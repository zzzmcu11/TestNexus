"""
断点续传管理器
负责管理分析过程中的恢复点，确保系统中断后能够从上次停止的地方继续
"""
import os
import json
import hashlib
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class ResumeManager:
    """断点续传管理器"""
    
    def __init__(self, base_dir: str = None):
        """
        初始化恢复管理器
        
        Args:
            base_dir: 恢复点保存的基础目录，如果为None则使用临时目录
        """
        if base_dir is None:
            # 获取项目根目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            self.resume_dir = os.path.join(project_root, 'resume_points')
        else:
            self.resume_dir = base_dir
        
        # 确保恢复点目录存在
        os.makedirs(self.resume_dir, exist_ok=True)
        
        logger.info(f"[{self._format_time()}] 初始化恢复管理器，恢复点目录: {self.resume_dir}")
    
    def _format_time(self) -> str:
        """格式化当前时间"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def calculate_document_hash(self, document_text: str, model_name: str = None) -> str:
        """
        计算文档的唯一哈希值，用于标识分析任务
        
        Args:
            document_text: 文档文本
            model_name: 模型名称
            
        Returns:
            文档哈希值
        """
        # 组合文档文本和模型名称作为哈希输入
        hash_input = f"{document_text}:{model_name or 'default'}"
        
        # 使用SHA256计算哈希
        hash_obj = hashlib.sha256(hash_input.encode('utf-8'))
        document_hash = hash_obj.hexdigest()[:16]  # 取前16位作为短哈希
        
        logger.debug(f"[{self._format_time()}] 计算文档哈希: {document_hash}")
        return document_hash
    
    def save_resume_point(
        self,
        document_hash: str,
        test_points: List[Dict[str, Any]],
        test_cases: List[Dict[str, Any]],
        current_index: int,
        analysis_summary: Dict[str, Any],
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        保存恢复点
        
        Args:
            document_hash: 文档哈希
            test_points: 已生成的测试点列表
            test_cases: 已生成的测试用例列表
            current_index: 当前处理到的测试点索引
            analysis_summary: 分析摘要
            metadata: 额外元数据
            
        Returns:
            恢复点文件路径
        """
        # 构建恢复点数据
        resume_data = {
            "document_hash": document_hash,
            "test_points": test_points,
            "test_cases": test_cases,
            "current_index": current_index,
            "analysis_summary": analysis_summary,
            "metadata": metadata or {},
            "timestamp": self._format_time(),
            "total_points": len(test_points),
            "completed_points": current_index,
            "completed_cases": len(test_cases)
        }
        
        # 生成恢复点文件名
        resume_filename = f"resume_{document_hash}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        resume_path = os.path.join(self.resume_dir, resume_filename)
        
        # 保存恢复点
        with open(resume_path, 'w', encoding='utf-8') as f:
            json.dump(resume_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"[{self._format_time()}] 保存恢复点: {resume_filename}")
        logger.info(f"[{self._format_time()}] 进度: {current_index}/{len(test_points)} 个测试点, {len(test_cases)} 个测试用例")
        
        return resume_path
    
    def load_resume_point(self, document_hash: str) -> Optional[Dict[str, Any]]:
        """
        加载最近的恢复点
        
        Args:
            document_hash: 文档哈希
            
        Returns:
            恢复点数据，如果不存在则返回None
        """
        # 查找匹配的恢复点文件
        resume_files = []
        for filename in os.listdir(self.resume_dir):
            if filename.startswith(f"resume_{document_hash}_") and filename.endswith('.json'):
                resume_files.append(filename)
        
        if not resume_files:
            logger.info(f"[{self._format_time()}] 未找到文档 {document_hash} 的恢复点")
            return None
        
        # 按时间戳排序，获取最新的恢复点
        resume_files.sort(reverse=True)
        latest_resume = resume_files[0]
        resume_path = os.path.join(self.resume_dir, latest_resume)
        
        try:
            with open(resume_path, 'r', encoding='utf-8') as f:
                resume_data = json.load(f)
            
            logger.info(f"[{self._format_time()}] 加载恢复点: {latest_resume}")
            logger.info(f"[{self._format_time()}] 恢复进度: {resume_data['completed_points']}/{resume_data['total_points']} 个测试点, "
                       f"{resume_data['completed_cases']} 个测试用例")
            
            return resume_data
        except Exception as e:
            logger.error(f"[{self._format_time()}] 加载恢复点失败: {e}")
            return None
    
    def get_resume_progress(self, document_hash: str) -> Tuple[int, int, int]:
        """
        获取恢复进度
        
        Args:
            document_hash: 文档哈希
            
        Returns:
            (总测试点数, 已完成测试点数, 已完成测试用例数)
        """
        resume_data = self.load_resume_point(document_hash)
        if resume_data:
            return (
                resume_data['total_points'],
                resume_data['completed_points'],
                resume_data['completed_cases']
            )
        return (0, 0, 0)
    
    def delete_resume_point(self, document_hash: str) -> bool:
        """
        删除指定文档的所有恢复点
        
        Args:
            document_hash: 文档哈希
            
        Returns:
            是否删除成功
        """
        deleted_count = 0
        for filename in os.listdir(self.resume_dir):
            if filename.startswith(f"resume_{document_hash}_") and filename.endswith('.json'):
                try:
                    os.remove(os.path.join(self.resume_dir, filename))
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"[{self._format_time()}] 删除恢复点 {filename} 失败: {e}")
        
        logger.info(f"[{self._format_time()}] 删除文档 {document_hash} 的 {deleted_count} 个恢复点")
        return deleted_count > 0
    
    def cleanup_old_resume_points(self, max_age_hours: int = 24):
        """
        清理旧的恢复点文件
        
        Args:
            max_age_hours: 最大保留时间（小时）
        """
        now = datetime.now()
        deleted_count = 0
        
        for filename in os.listdir(self.resume_dir):
            if filename.startswith("resume_") and filename.endswith('.json'):
                file_path = os.path.join(self.resume_dir, filename)
                
                try:
                    # 从文件名中提取时间戳
                    # 格式: resume_{hash}_{YYYYMMDD}_{HHMMSS}.json
                    parts = filename.split('_')
                    if len(parts) >= 4:
                        timestamp_str = f"{parts[2]}_{parts[3].split('.')[0]}"
                        file_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                        
                        # 计算文件年龄
                        age_hours = (now - file_time).total_seconds() / 3600
                        
                        if age_hours > max_age_hours:
                            os.remove(file_path)
                            deleted_count += 1
                            logger.debug(f"[{self._format_time()}] 清理旧恢复点: {filename}")
                except Exception as e:
                    logger.error(f"[{self._format_time()}] 处理恢复点 {filename} 失败: {e}")
        
        if deleted_count > 0:
            logger.info(f"[{self._format_time()}] 清理了 {deleted_count} 个旧恢复点")

# 单例实例
_resume_manager_instance = None

def get_resume_manager() -> ResumeManager:
    """获取恢复管理器单例实例"""
    global _resume_manager_instance
    if _resume_manager_instance is None:
        _resume_manager_instance = ResumeManager()
    return _resume_manager_instance

if __name__ == "__main__":
    # 测试代码
    manager = ResumeManager()
    
    # 测试文档哈希计算
    test_doc = "这是一个测试文档"
    doc_hash = manager.calculate_document_hash(test_doc, "test-model")
    print(f"文档哈希: {doc_hash}")
    
    # 测试恢复点管理
    test_resume = manager.load_resume_point(doc_hash)
    print(f"恢复点: {test_resume}")
    
    # 清理旧文件
    manager.cleanup_old_resume_points()
