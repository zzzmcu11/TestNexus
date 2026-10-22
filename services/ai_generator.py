import json
import os
import logging
import re
import hashlib
import tempfile
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Callable
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.exceptions import OutputParserException
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# 导入断点续传管理器
try:
    from .resume_manager import get_resume_manager
    RESUME_MANAGER_AVAILABLE = True
except ImportError:
    RESUME_MANAGER_AVAILABLE = False
    logging.warning("[Resume Manager] 无法导入断点续传管理器，断点续传功能将不可用")

# Load environment variables
load_dotenv()

# Setup logging using new logging configuration
try:
    from logging_config import setup_logging, get_logger
    setup_logging()
except ImportError:
    # Fallback to basic logging if new config is not available
    logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

def beijing_time() -> datetime:
    """获取北京时间 (UTC+8)"""
    utc_now = datetime.now(timezone.utc)
    beijing_tz = timezone(timedelta(hours=8))
    return utc_now.astimezone(beijing_tz)

def format_beijing_time() -> str:
    """格式化北京时间字符串"""
    return beijing_time().strftime("%Y-%m-%d %H:%M:%S %Z")

def initialize_model(model_name: str = None):
    """
    Initialize the ChatOpenAI model for various AI providers
    
    Args:
        model_name: 模型名称，如果不指定则从环境变量读取
        
    Returns:
        ChatOpenAI 实例
    """
    # 确定模型名称
    if not model_name:
        model_name = os.getenv("MODEL_NAME", "deepseek-reasoner")
    
    # 根据模型类型选择API密钥和基础URL
    model_lower = model_name.lower()
    
    # 默认配置
    api_key = None
    base_url = None
    
    # 如果是Qwen模型
    if "qwen" in model_lower:
        # 优先使用QWEN_API_KEY
        api_key = os.getenv("QWEN_API_KEY")
        if not api_key:
            # 回退到通用API_KEY
            api_key = os.getenv("AI_API_KEY")
        
        # 使用QWEN_BASE_URL或默认的DashScope端点
        base_url = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        
        logger.info(f"使用Qwen模型配置: {model_name}")
    
    # 如果是DeepSeek模型
    elif "deepseek" in model_lower:
        # 优先使用DEEPSEEK_API_KEY
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            # 回退到通用API_KEY
            api_key = os.getenv("AI_API_KEY")
        
        # 使用BASE_URL或默认的DeepSeek端点
        base_url = os.getenv("BASE_URL", "https://api.deepseek.com")
        
        logger.info(f"使用DeepSeek模型配置: {model_name}")
    
    # 如果是硅基流动模型
    elif "siliconflow" in model_lower:
        # 优先使用SILICONFLOW_API_KEY
        api_key = os.getenv("SILICONFLOW_API_KEY")
        if not api_key:
            # 回退到通用API_KEY
            api_key = os.getenv("AI_API_KEY")
        
        # 使用SILICONFLOW_BASE_URL或默认的SiliconFlow端点
        base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
        
        # 使用SILICONFLOW_MODEL_NAME或默认模型名称
        model_name = os.getenv("SILICONFLOW_MODEL_NAME", "deepseek-ai/DeepSeek-V3.2-Exp")
        
        logger.info(f"使用硅基流动模型配置: {model_name}, base_url: {base_url}")
    
    # 其他模型（如GPT-4）
    else:
        # 使用通用配置
        api_key = os.getenv("AI_API_KEY")
        base_url = os.getenv("BASE_URL", "https://api.siliconflow.cn/v1/chat/completions")
        
        logger.info(f"使用通用模型配置: {model_name}")
    
    # 如果还没有API密钥，抛出错误
    if not api_key:
        error_msg = f"API key not found for model {model_name}. "
        if "qwen" in model_lower:
            error_msg += "Please set QWEN_API_KEY or AI_API_KEY in environment variables."
        elif "deepseek" in model_lower:
            error_msg += "Please set DEEPSEEK_API_KEY or AI_API_KEY in environment variables."
        elif "siliconflow" in model_lower:
            error_msg += "Please set SILICONFLOW_API_KEY or AI_API_KEY in environment variables."
        else:
            error_msg += "Please set AI_API_KEY in environment variables."
        raise ValueError(error_msg)
    
    # 如果没有基础URL，使用默认值
    if not base_url:
        base_url = "https://api.deepseek.com"
    
    temperature = float(os.getenv("TEMPERATURE", "0.1"))
    
    # 构建模型配置 - 硬编码参数
    model_config = {
        "model": model_name,
        "base_url": base_url,
        "api_key": api_key,
        "temperature": temperature,
        "max_tokens": 4096,
        "top_p": 0.5,
        "frequency_penalty": 0.2,
        "presence_penalty": 0.1,
    }
    
    model = ChatOpenAI(**model_config)
    
    logger.info(f"初始化模型: {model_name}, 温度: {temperature}, base_url: {base_url}")
    
    return model

# Initialize the default model
try:
    default_model = initialize_model()
except Exception as e:
    default_model = None
    logger.error(f"模型初始化失败: {e}")

def extract_json_from_text(text: str):
    """
    从文本中提取JSON内容，处理常见的非标准JSON响应
    """
    if not text:
        return None
    
    # 如果文本已经是有效的JSON，直接返回
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    # 尝试提取被 ```json ... ``` 包裹的JSON
    json_block_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
    matches = re.findall(json_block_pattern, text)
    for match in matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue
    
    # 尝试提取被 ``` ... ``` 包裹的内容（无json标记）
    if not matches:
        generic_block_pattern = r'```\s*([\s\S]*?)\s*```'
        matches = re.findall(generic_block_pattern, text)
        for match in matches:
            # 检查是否是JSON对象或数组
            trimmed = match.strip()
            if (trimmed.startswith('{') and trimmed.endswith('}')) or \
               (trimmed.startswith('[') and trimmed.endswith(']')):
                try:
                    return json.loads(trimmed)
                except json.JSONDecodeError:
                    continue
    
    # 尝试提取第一个完整的JSON对象或数组
    # 查找以 { 开头，以 } 结尾的字符串
    json_obj_pattern = r'\{[^{}]*\}(?=\s*(?:\{|$))'
    obj_matches = re.findall(json_obj_pattern, text, re.DOTALL)
    for match in obj_matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue
    
    # 查找以 [ 开头，以 ] 结尾的字符串
    json_array_pattern = r'\[[^\[\]]*\]'
    array_matches = re.findall(json_array_pattern, text, re.DOTALL)
    for match in array_matches:
        try:
            return json.loads(match)
        except json.JSONDecodeError:
            continue
    
    # 如果以上都不行，尝试将整个文本作为可能的不完整JSON处理
    # 移除可能的开头文本（如"好的，我将..."等）
    lines = text.split('\n')
    json_start = -1
    for i, line in enumerate(lines):
        if line.strip().startswith('{') or line.strip().startswith('['):
            json_start = i
            break
    
    if json_start >= 0:
        json_text = '\n'.join(lines[json_start:])
        try:
            return json.loads(json_text)
        except json.JSONDecodeError:
            pass
    
    # 最后尝试：如果文本看起来像是JSON但有多余字符，尝试清理
    # 移除所有非JSON字符（保留 {}[]",: 和字母数字空格）
    cleaned = re.sub(r'[^\{\}\[\]",:\w\s]', '', text)
    # 尝试找到最长的可能JSON
    for i in range(len(cleaned)):
        for j in range(len(cleaned), i, -1):
            substr = cleaned[i:j]
            if substr.startswith('{') and substr.endswith('}'):
                try:
                    return json.loads(substr)
                except json.JSONDecodeError:
                    continue
            elif substr.startswith('[') and substr.endswith(']'):
                try:
                    return json.loads(substr)
                except json.JSONDecodeError:
                    continue
    
    raise ValueError("无法从响应中提取有效的JSON")

def load_prompt_from_file(filename: str) -> str:
    """
    从prompts目录加载提示词文件
    使用相对于项目根目录的路径
    """
    # 获取当前文件所在目录 (services目录)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 获取项目根目录 (ai_test_system目录)
    project_root = os.path.dirname(current_dir)
    # 构建prompts目录的完整路径
    prompts_dir = os.path.join(project_root, 'prompts')
    prompt_path = os.path.join(prompts_dir, filename)
    
    if os.path.exists(prompt_path):
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    else:
        # 如果文件不存在，返回默认提示词
        logger.warning(f"提示词文件不存在: {prompt_path}")
        if filename == 'analysis_prompt.txt':
            return """你是一名经验丰富的业务分析师，专门从事软件需求分析和测试计划。

你的任务是分析提供的软件需求文档，并将其分解为原子级的、可测试的逻辑单元，称为"测试点"。

关键说明：
1. 逐步思考：在生成任何输出之前，仔细分析需求。
2. 分解：将复杂需求分解为更小、独立的可测试单元。
3. 识别边界情况：针对每个测试点，考虑边界条件、错误场景和异常使用模式。
4. 分类：按功能区域（例如，认证、支付、UI/UX、性能、安全性）对测试点进行分组。
5. 优先级排序：根据业务影响和风险分配适当的优先级（critical, high, medium, low）。
6. 结构化输出：你的响应必须是符合指定架构的有效JSON对象。

每个测试点应包括：
- id: 唯一标识符（例如，"TP-001"）
- category: 功能类别
- description: 清晰、简洁的描述，说明要测试的内容
- priority: critical, high, medium, 或 low
- requirements_ref: 对需求文本的具体引用
- edge_cases: 要考虑的潜在边界情况列表

专注于完整性和可测试性。确保覆盖所有需求。"""
        elif filename == 'generation_prompt.txt':
            return """# Role Definition
你是一位拥有10年经验的资深QA工程师（SDET），精通黑盒测试、白盒测试、边界值分析、等价类划分以及错误猜测法。你擅长发现软件中潜藏的逻辑漏洞、安全隐患和用户体验问题。

# Task Objective
请根据给定的测试点，编写一份详尽、覆盖全面的测试用例（Test Cases）。

# Thinking Framework (你需要遵循的测试维度)
在编写用例时，必须严格按照以下维度进行思考，不要仅局限于"快乐路径（Happy Path）"：

1.  **功能测试 (Functional)**:
    -   正向测试：输入有效数据，验证功能是否按预期工作。
    -   逆向测试：输入无效数据、空值、超长字符、特殊符号，验证系统的错误处理机制。
2.  **边界值分析 (Boundary Analysis)**:
    -   测试最大值、最小值、最大值+1、最小值-1、零值等临界状态。
3.  **逻辑流程 (Logical Flow)**:
    -   测试业务状态的流转（例如：订单从"待支付"到"已取消"是否合法）。
    -   测试中断流程（例如：操作过程中断网或强制退出）。
4.  **数据完整性 (Data Integrity)**:
    -   验证数据在数据库中的存储是否正确，增删改查（CRUD）后的数据一致性。
5.  **安全性 (Security) [如果适用]**:
    -   权限控制（越权访问）、SQL注入尝试、XSS尝试、敏感数据加密。
6.  **兼容性与UI (Compatibility & UI) [如果适用]**:
    -   不同分辨率、浏览器、设备下的表现，以及UI交互反馈（Loading、Toast提示）。

# Output Rules (输出约束)
1.  **格式要求**: 请使用 json 形式输出，使测试用例可重用、可维护且易于自动化。
2.  **语言风格**: 使用简洁、专业的技术术语，步骤必须原子化（Atomic），不可模棱两可。
3.  **前置条件**: 必须明确执行该用例前所需的系统状态。
4.  **优先级**: P0 (阻塞级), P1 (核心功能), P2 (普通功能), P3 (UI/微小建议)。
5.  **每个测试用例应包括**：
    - test_case_id: 唯一标识符（例如，"TC-001"）
    - linked_point_id: 此用例验证的测试点ID
    - title: 描述性的测试用例标题
    - preconditions: 必须满足的条件列表
    - steps: 逐步说明
    - expected_result: 预期结果
    - test_data: 任何所需的测试数据"""
        else:
            return ""

# Load prompts from files
ANALYSIS_SYSTEM_PROMPT = load_prompt_from_file('analysis_prompt.txt')
GENERATION_SYSTEM_PROMPT = load_prompt_from_file('generation_prompt.txt')

# Human message templates
ANALYSIS_HUMAN_TEMPLATE = """需求文档：
{document}

分析上述需求并提取测试点。逐步思考，然后输出JSON。"""

GENERATION_HUMAN_TEMPLATE = """测试点：
{test_point}

为此测试点创建详细的测试用例。逐步思考，然后输出JSON。"""

# Create prompts
analysis_prompt = ChatPromptTemplate.from_messages([
    ("system", ANALYSIS_SYSTEM_PROMPT),
    ("human", ANALYSIS_HUMAN_TEMPLATE)
])

generation_prompt = ChatPromptTemplate.from_messages([
    ("system", GENERATION_SYSTEM_PROMPT),
    ("human", GENERATION_HUMAN_TEMPLATE)
])

# Define output schemas
analysis_schema = {
    "type": "object",
    "properties": {
        "test_points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "category": {"type": "string"},
                    "description": {"type": "string"},
                    "priority": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                    "requirements_ref": {"type": "string"},
                    "edge_cases": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["id", "category", "description", "priority", "requirements_ref", "edge_cases"]
            }
        },
        "summary": {
            "type": "object",
            "properties": {
                "total_test_points": {"type": "integer"},
                "critical_count": {"type": "integer"},
                "high_count": {"type": "integer"},
                "medium_count": {"type": "integer"},
                "low_count": {"type": "integer"}
            }
        }
    },
    "required": ["test_points", "summary"]
}

generation_schema = {
    "type": "object",
    "properties": {
        "test_cases": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "test_case_id": {"type": "string"},
                    "linked_point_id": {"type": "string"},
                    "title": {"type": "string"},
                    "preconditions": {"type": "array", "items": {"type": "string"}},
                    "steps": {"type": "array", "items": {"type": "string"}},
                    "expected_result": {"type": "string"},
                    "test_data": {"type": "string"}
                },
                "required": ["test_case_id", "linked_point_id", "title", "preconditions", "steps", "expected_result", "test_data"]
            }
        }
    },
    "required": ["test_cases"]
}

def generate_test_cases_with_resume(
    document_text: str, 
    model_name: str = None,
    progress_callback: Optional[Callable[[str, float], None]] = None,
    enable_resume: bool = True
) -> Dict[str, Any]:
    """
    主函数：处理需求文档，生成测试点和测试用例，支持进度回调和断点续传
    
    Args:
        document_text: 清洗后的需求文档文本
        model_name: 使用的模型名称，如果为None则使用默认模型
        progress_callback: 进度回调函数，接收(消息, 进度百分比)
        enable_resume: 是否启用断点续传功能
        
    Returns:
        包含测试点和测试用例的字典
    """
    # 选择模型
    current_model = default_model
    if model_name and model_name != os.getenv("MODEL_NAME", "deepseek-reasoner"):
        try:
            current_model = initialize_model(model_name)
            logger.info(f"切换到模型: {model_name}")
        except Exception as e:
            logger.error(f"切换模型失败，使用默认模型: {e}")
            current_model = default_model
    
    if current_model is None:
        raise Exception("AI model is not initialized. Please check your API key and configuration.")
    
    def update_progress(message: str, progress: float = None):
        """更新进度"""
        logger.info(f"{message}")
        if progress_callback:
            progress_callback(message, progress)
    
    # 断点续传相关变量
    resume_manager = None
    document_hash = None
    resume_data = None
    start_index = 0
    existing_test_cases = []
    existing_analysis_summary = {}
    
    # 如果启用了断点续传，尝试加载恢复点
    if enable_resume and RESUME_MANAGER_AVAILABLE:
        try:
            resume_manager = get_resume_manager()
            document_hash = resume_manager.calculate_document_hash(document_text, model_name)
            resume_data = resume_manager.load_resume_point(document_hash)
            
            if resume_data:
                # 从恢复点继续
                test_points = resume_data.get('test_points', [])
                existing_test_cases = resume_data.get('test_cases', [])
                existing_analysis_summary = resume_data.get('analysis_summary', {})
                start_index = resume_data.get('current_index', 0)
                total_points = len(test_points)
                completed_cases = len(existing_test_cases)
                
                update_progress(f"检测到恢复点，从 {start_index}/{total_points} 继续...", 5)
                update_progress(f"已恢复 {completed_cases} 个测试用例", 5)
                
                # 直接使用恢复的测试点和分析摘要
                analysis_summary = existing_analysis_summary
                test_cases_all = existing_test_cases
                
                # 跳过分析文档步骤，直接进入测试用例生成
                update_progress(f"恢复分析摘要: {analysis_summary}", 10)
                update_progress(f"文档分析完成，提取到 {len(test_points)} 个测试点", 30)
                
                # 跳转到测试用例生成部分
                return _generate_test_cases_from_index(
                    test_points=test_points,
                    test_cases_all=test_cases_all,
                    start_index=start_index,
                    current_model=current_model,
                    analysis_summary=analysis_summary,
                    update_progress=update_progress,
                    document_text=document_text,
                    model_name=model_name,
                    resume_manager=resume_manager,
                    document_hash=document_hash,
                    enable_resume=enable_resume
                )
                
        except Exception as e:
            logger.error(f"断点续传初始化失败: {e}")
            # 继续正常流程
            pass
    
    # 如果没有恢复点或恢复失败，从头开始
    # 暂时简化：直接调用内部生成函数，忽略断点续传
    return _generate_test_cases_internal(
        document_text=document_text,
        model_name=model_name,
        current_model=current_model,
        update_progress=update_progress
    )

def _generate_test_cases_internal(
    document_text: str,
    model_name: str = None,
    current_model: ChatOpenAI = None,
    update_progress: Callable[[str, float], None] = None
) -> Dict[str, Any]:
    """
    内部函数：实际执行文档分析和测试用例生成
    """
    try:
        # Step 1: 分析文档，提取测试点
        update_progress("开始分析文档并提取测试点...", 10)
        analysis_chain = analysis_prompt | current_model | JsonOutputParser(pydantic_object=None)
        
        # 为了处理长文档，可以截断或分块，这里简单处理
        analysis_result = analysis_chain.invoke({"document": document_text})
        
        # 处理不同模型返回的不同格式
        if isinstance(analysis_result, dict):
            test_points = analysis_result.get('test_points', [])
            analysis_summary = analysis_result.get('summary', {})
        elif isinstance(analysis_result, list):
            # 如果直接返回测试点列表
            test_points = analysis_result
            analysis_summary = {}
            # 尝试从列表中提取summary信息
            analysis_summary = {
                "total_test_points": len(test_points),
                "critical_count": sum(1 for tp in test_points if tp.get('priority') == 'critical'),
                "high_count": sum(1 for tp in test_points if tp.get('priority') == 'high'),
                "medium_count": sum(1 for tp in test_points if tp.get('priority') == 'medium'),
                "low_count": sum(1 for tp in test_points if tp.get('priority') == 'low')
            }
        else:
            # 未知格式，转换为列表
            logger.warning(f"未知的分析结果格式: {type(analysis_result)}")
            test_points = []
            analysis_summary = {}
        
        update_progress(f"文档分析完成，提取到 {len(test_points)} 个测试点", 30)
        
        # 实时发送测试点数据
        if update_progress and hasattr(update_progress, '_stream_callback'):
            try:
                update_progress._stream_callback('test_points', test_points)
            except Exception as e:
                logger.warning(f"发送测试点数据失败: {e}")
        
        # Step 2: 为每个测试点生成测试用例
        test_cases_all = []
        total_points = len(test_points)
        
        update_progress(f"开始为 {total_points} 个测试点生成测试用例...", 40)
        
        for idx, test_point in enumerate(test_points):
            point_id = test_point.get('id', f"TP-{idx+1:03d}")
            category = test_point.get('category', '未知')
            
            try:
                # 更新进度
                progress = 40 + (idx / total_points) * 50  # 40% - 90%
                update_progress(f"正在为测试点 {point_id} ({category}) 生成测试用例... ({idx+1}/{total_points})", progress)
                
                # 为每个测试点生成测试用例 - 使用自定义解析以处理非标准JSON响应
                generation_chain = generation_prompt | current_model
                
                # 将测试点转换为字符串表示
                test_point_str = json.dumps(test_point, ensure_ascii=False)
                
                # 添加超时和重试机制
                max_retries = 2
                generation_raw_result = None
                for retry in range(max_retries):
                    try:
                        generation_raw_result = generation_chain.invoke({"test_point": test_point_str})
                        break
                    except Exception as e:
                        if retry == max_retries - 1:
                            raise e
                        retry_msg = f"测试点 {point_id} 重试 {retry+1}/{max_retries}: {str(e)[:100]}"
                        update_progress(retry_msg, progress)
                        import time
                        time.sleep(1)
                
                # 解析响应
                generation_result = None
                if generation_raw_result:
                    try:
                        # 首先尝试使用我们的JSON提取函数
                        generation_result = extract_json_from_text(generation_raw_result.content)
                        logger.info(f"测试点 {point_id} 成功解析响应")
                    except Exception as parse_error:
                        # 如果解析失败，记录错误并尝试其他方法
                        logger.warning(f"测试点 {point_id} JSON解析失败: {parse_error}")
                        # 尝试将原始响应作为文本处理
                        if hasattr(generation_raw_result, 'content'):
                            generation_result = generation_raw_result.content
                        else:
                            generation_result = str(generation_raw_result)
                
                # 添加生成的测试用例 - 处理不同格式的响应
                if generation_result:
                    # 尝试从不同格式中提取测试用例
                    generated_cases = []
                    
                    # 格式1: 直接包含'test_cases'字段
                    if isinstance(generation_result, dict) and 'test_cases' in generation_result:
                        generated_cases = generation_result.get('test_cases', [])
                    
                    # 格式2: 整个响应就是测试用例列表
                    elif isinstance(generation_result, list):
                        generated_cases = generation_result
                    
                    # 格式3: 其他可能的结构
                    elif isinstance(generation_result, dict):
                        # 尝试查找包含测试用例的任何字段
                        for key, value in generation_result.items():
                            if isinstance(value, list) and len(value) > 0:
                                # 检查列表中的元素是否有类似测试用例的结构
                                sample = value[0] if value else {}
                                if isinstance(sample, dict):
                                    # 检查是否有测试用例的关键字段
                                    test_case_fields = ['test_case_id', 'title', 'steps', 'expected_result', 'preconditions']
                                    if any(field in sample for field in test_case_fields):
                                        generated_cases = value
                                        logger.info(f"从字段 '{key}' 中提取到 {len(generated_cases)} 个测试用例")
                                        break
                    
                    # 如果还没有找到，尝试更通用的搜索
                    if not generated_cases and isinstance(generation_result, dict):
                        # 查找任何包含测试用例数据的字段
                        for key, value in generation_result.items():
                            if isinstance(value, dict):
                                # 检查这个字典是否有测试用例字段
                                test_case_fields = ['test_case_id', 'title', 'steps', 'expected_result', 'preconditions']
                                if any(field in value for field in test_case_fields):
                                    generated_cases = [value]
                                    logger.info(f"从字典字段 '{key}' 中提取到测试用例")
                                    break
                    
                    # 如果还没有找到，尝试将整个响应作为一个测试用例
                    if not generated_cases and isinstance(generation_result, dict):
                        test_case_fields = ['test_case_id', 'title', 'steps', 'expected_result', 'preconditions']
                        if any(field in generation_result for field in test_case_fields):
                            generated_cases = [generation_result]
                            logger.info(f"将整个响应作为一个测试用例")
                    
                    if generated_cases:
                        # 确保每个测试用例都有linked_point_id
                        for case in generated_cases:
                            if isinstance(case, dict) and 'linked_point_id' not in case:
                                case['linked_point_id'] = point_id
                        test_cases_all.extend(generated_cases)
                        update_progress(f"测试点 {point_id} 生成完成，生成 {len(generated_cases)} 个测试用例", progress)
                        # 记录成功信息
                        logger.info(f"测试点 {point_id} 成功生成 {len(generated_cases)} 个测试用例")
                        
                        # 实时发送测试用例数据
                        if update_progress and hasattr(update_progress, '_stream_callback'):
                            try:
                                update_progress._stream_callback('test_cases', generated_cases)
                            except Exception as e:
                                logger.warning(f"发送测试用例数据失败: {e}")
                    else:
                        # 记录详细的调试信息
                        logger.warning(f"测试点 {point_id} 生成的响应格式无法解析")
                        logger.warning(f"响应类型: {type(generation_result)}")
                        logger.warning(f"响应内容 (前500字符): {str(generation_result)[:500]}")
                        update_progress(f"警告：测试点 {point_id} 生成的响应格式无法解析", progress)
                else:
                    logger.warning(f"测试点 {point_id} 未生成任何响应")
                    update_progress(f"警告：测试点 {point_id} 未生成任何响应", progress)
                    
            except Exception as e:
                error_msg = f"测试点 {point_id} 生成测试用例失败: {str(e)[:200]}"
                update_progress(error_msg, progress)
                # 继续处理其他测试点，而不是整个失败
                continue
        
        # 构建最终结果
        result = {
            "document_summary": {
                "total_characters": len(document_text),
                "total_test_points": len(test_points),
                "total_test_cases": len(test_cases_all)
            },
            "test_points": test_points,
            "test_cases": test_cases_all,
            "analysis_summary": analysis_summary,
            "model_used": current_model.model_name if hasattr(current_model, 'model_name') else "unknown"
        }
        
        update_progress(f"所有测试点处理完成，共生成 {len(test_cases_all)} 个测试用例", 100)
        
        return result
    
    except OutputParserException as e:
        error_msg = f"解析AI响应失败: {e}"
        update_progress(error_msg, 0)
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"AI生成错误: {e}"
        update_progress(error_msg, 0)
        raise Exception(error_msg)


def _generate_test_cases_from_index(
    test_points: List[Dict[str, Any]],
    test_cases_all: List[Dict[str, Any]],
    start_index: int,
    current_model: ChatOpenAI,
    analysis_summary: Dict[str, Any],
    update_progress: Callable[[str, float], None],
    document_text: str,
    model_name: str = None,
    resume_manager = None,
    document_hash: str = None,
    enable_resume: bool = True
) -> Dict[str, Any]:
    """
    从指定索引继续生成测试用例（用于断点续传）
    """
    total_points = len(test_points)
    
    for idx in range(start_index, total_points):
        test_point = test_points[idx]
        point_id = test_point.get('id', f"TP-{idx+1:03d}")
        category = test_point.get('category', '未知')
        
        try:
            # 更新进度
            progress = 40 + (idx / total_points) * 50  # 40% - 90%
            update_progress(f"正在为测试点 {point_id} ({category}) 生成测试用例... ({idx+1}/{total_points})", progress)
            
            # 为每个测试点生成测试用例
            generation_chain = generation_prompt | current_model
            test_point_str = json.dumps(test_point, ensure_ascii=False)
            
            # 添加超时和重试机制
            max_retries = 2
            generation_raw_result = None
            for retry in range(max_retries):
                try:
                    generation_raw_result = generation_chain.invoke({"test_point": test_point_str})
                    break
                except Exception as e:
                    if retry == max_retries - 1:
                        raise e
                    retry_msg = f"测试点 {point_id} 重试 {retry+1}/{max_retries}: {str(e)[:100]}"
                    update_progress(retry_msg, progress)
                    import time
                    time.sleep(1)
            
            # 解析响应
            generation_result = None
            if generation_raw_result:
                try:
                    generation_result = extract_json_from_text(generation_raw_result.content)
                    logger.info(f"测试点 {point_id} 成功解析响应")
                except Exception as parse_error:
                    logger.warning(f"测试点 {point_id} JSON解析失败: {parse_error}")
                    if hasattr(generation_raw_result, 'content'):
                        generation_result = generation_raw_result.content
                    else:
                        generation_result = str(generation_raw_result)
            
            # 添加生成的测试用例
            if generation_result:
                generated_cases = []
                
                if isinstance(generation_result, dict) and 'test_cases' in generation_result:
                    generated_cases = generation_result.get('test_cases', [])
                elif isinstance(generation_result, list):
                    generated_cases = generation_result
                elif isinstance(generation_result, dict):
                    # 尝试查找包含测试用例的任何字段
                    for key, value in generation_result.items():
                        if isinstance(value, list) and len(value) > 0:
                            sample = value[0] if value else {}
                            if isinstance(sample, dict):
                                test_case_fields = ['test_case_id', 'title', 'steps', 'expected_result', 'preconditions']
                                if any(field in sample for field in test_case_fields):
                                    generated_cases = value
                                    break
                
                if generated_cases:
                    for case in generated_cases:
                        if isinstance(case, dict) and 'linked_point_id' not in case:
                            case['linked_point_id'] = point_id
                    test_cases_all.extend(generated_cases)
                    update_progress(f"测试点 {point_id} 生成完成，生成 {len(generated_cases)} 个测试用例", progress)
                    logger.info(f"测试点 {point_id} 成功生成 {len(generated_cases)} 个测试用例")
                else:
                    logger.warning(f"测试点 {point_id} 生成的响应格式无法解析")
                    update_progress(f"警告：测试点 {point_id} 生成的响应格式无法解析", progress)
            else:
                logger.warning(f"测试点 {point_id} 未生成任何响应")
                update_progress(f"警告：测试点 {point_id} 未生成任何响应", progress)
                
        except Exception as e:
            error_msg = f"测试点 {point_id} 生成测试用例失败: {str(e)[:200]}"
            update_progress(error_msg, progress)
            continue
        
        # 保存恢复点（如果启用了断点续传）
        if enable_resume and resume_manager and document_hash:
            try:
                resume_manager.save_resume_point(
                    document_hash=document_hash,
                    test_points=test_points,
                    test_cases=test_cases_all,
                    current_index=idx + 1,  # 下一个要处理的索引
                    analysis_summary=analysis_summary,
                    metadata={"model_name": model_name}
                )
            except Exception as e:
                logger.warning(f"保存恢复点失败: {e}")
    
    # 构建最终结果
    result = {
        "document_summary": {
            "total_characters": len(document_text),
            "total_test_points": len(test_points),
            "total_test_cases": len(test_cases_all)
        },
        "test_points": test_points,
        "test_cases": test_cases_all,
        "analysis_summary": analysis_summary,
        "model_used": current_model.model_name if hasattr(current_model, 'model_name') else "unknown"
    }
    
    update_progress(f"所有测试点处理完成，共生成 {len(test_cases_all)} 个测试用例", 100)
    
    # 删除恢复点（分析完成）
    if enable_resume and resume_manager and document_hash:
        try:
            resume_manager.delete_resume_point(document_hash)
            logger.info(f"分析完成，删除恢复点")
        except Exception as e:
            logger.warning(f"删除恢复点失败: {e}")
    
    return result


def generate_test_cases_with_progress(
    document_text: str, 
    model_name: str = None,
    progress_callback: Optional[Callable[[str, float], None]] = None
) -> Dict[str, Any]:
    """
    主函数：处理需求文档，生成测试点和测试用例，支持进度回调
    向后兼容版本，调用新的断点续传功能
    
    Args:
        document_text: 清洗后的需求文档文本
        model_name: 使用的模型名称，如果为None则使用默认模型
        progress_callback: 进度回调函数，接收(消息, 进度百分比)
        
    Returns:
        包含测试点和测试用例的字典
    """
    return generate_test_cases_with_resume(
        document_text=document_text,
        model_name=model_name,
        progress_callback=progress_callback,
        enable_resume=False  # 向后兼容，默认不启用断点续传
    )


# 为了向后兼容，保留原函数
def generate_test_cases(document_text: str) -> Dict[str, Any]:
    """向后兼容的原函数"""
    return generate_test_cases_with_progress(document_text, progress_callback=None)

if __name__ == "__main__":
    # 测试代码
    sample_doc = """
    项目需求文档
    
    1. 用户登录功能
    - 用户应能够使用用户名和密码登录
    - 登录失败时显示适当的错误消息
    - 连续5次登录失败后锁定账户30分钟
    
    2. 数据导出功能
    - 用户应能够将报告导出为PDF和Excel格式
    - 导出文件应包含时间戳和用户信息
    - 大型报告导出应在后台处理
    
    3. 搜索功能
    - 用户应能够按日期范围、关键词和类别搜索记录
    - 搜索结果应分页显示，每页20条记录
    """
    
    try:
        result = generate_test_cases(sample_doc)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}")
