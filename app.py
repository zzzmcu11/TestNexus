from flask import Flask, render_template, request, jsonify, send_file, Response
import os
import logging
from services.doc_processor import process_document
from services.ai_generator import generate_test_cases_with_progress, generate_test_cases
from services.excel_exporter_fixed import export_to_excel_bytes
from services.history_manager import history_manager
import tempfile
import uuid
import json
from io import BytesIO
import time
from datetime import datetime
import shutil

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit

# Setup logging using new logging configuration
try:
    from logging_config import setup_logging, get_logger
    setup_logging()
except ImportError:
    # Fallback to basic logging if new config is not available
    logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

def beijing_time() -> str:
    """获取北京时间字符串"""
    from datetime import timezone, timedelta
    utc_now = datetime.now(timezone.utc)
    beijing_tz = timezone(timedelta(hours=8))
    return utc_now.astimezone(beijing_tz).strftime("%Y-%m-%d %H:%M:%S %Z")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """处理文件上传并生成测试用例（非流式版本）"""
    if 'file' not in request.files:
        return jsonify({'error': '没有找到文件部分'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400
    
    if not file.filename.endswith('.docx'):
        return jsonify({'error': '文件必须是 .docx 格式的文档'}), 400
    
    # 检查文件大小
    file_size = len(file.read())
    file.seek(0)  # 重置文件指针
    
    if file_size > 16 * 1024 * 1024:
        return jsonify({'error': '文件大小不能超过 16MB'}), 400
    
    # 保存上传的文件到临时目录
    file_id = str(uuid.uuid4())
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"{file_id}.docx")
    
    try:
        file.save(temp_path)
        logger.info(f"文件已保存到临时路径: {temp_path}")
    except Exception as e:
        logger.error(f"保存文件失败: {e}")
        return jsonify({'error': f'保存文件失败: {str(e)}'}), 500
    
    try:
        # 处理文档
        logger.info(f"开始处理文档: {file.filename}")
        document_text = process_document(temp_path)
        logger.info(f"文档处理完成，字符数: {len(document_text)}")
        
        # 生成测试用例
        logger.info(f"开始生成测试用例")
        result = generate_test_cases(document_text)
        logger.info(f"测试用例生成完成，生成 {len(result.get('test_points', []))} 个测试点和 {len(result.get('test_cases', []))} 个测试用例")
        
        # 保存到历史记录
        history_id = history_manager.add_analysis(
            document_text=document_text,
            analysis_result=result,
            original_filename=file.filename,
            user_notes=None
        )
        
        # 添加历史记录ID到结果中
        result['history_id'] = history_id
        result['original_filename'] = file.filename
        result['processed_at'] = beijing_time()
        
        # 清理临时文件
        if os.path.exists(temp_path):
            os.remove(temp_path)
            logger.info(f"临时文件已清理: {temp_path}")
        
        return jsonify(result)
    
    except ValueError as e:
        # 特定的值错误（如API密钥错误）
        logger.error(f"值错误: {e}")
        error_msg = str(e)
        if 'API_KEY' in error_msg:
            error_msg = "API密钥配置错误，请检查环境变量设置"
        return jsonify({'error': error_msg}), 500
    
    except Exception as e:
        # 通用异常处理
        logger.error(f"处理文档时发生错误: {e}", exc_info=True)
        error_msg = str(e)
        
        # 根据错误类型提供更友好的错误信息
        if 'timeout' in error_msg.lower():
            error_msg = "处理超时，请稍后重试或尝试较小的文档"
        elif 'connection' in error_msg.lower():
            error_msg = "网络连接错误，请检查网络连接或API服务状态"
        elif 'invalid' in error_msg.lower() or '格式' in error_msg:
            error_msg = "文档格式无效，请确保上传的是有效的.docx文件"
        
        return jsonify({'error': error_msg}), 500
    
    finally:
        # 确保临时文件被清理
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
                logger.info(f"最终清理临时文件: {temp_path}")
            except Exception as e:
                logger.warning(f"清理临时文件失败: {e}")

@app.route('/upload/stream', methods=['POST'])
def upload_file_stream():
    """
    流式上传和分析，使用Server-Sent Events (SSE)推送进度
    """
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if not file.filename.endswith('.docx'):
        return jsonify({'error': 'File must be a .docx document'}), 400
    
    # 获取选择的模型
    model_name = request.form.get('model_name', None)
    if model_name:
        logger.info(f"用户选择模型: {model_name}")
    
    # 确保files目录存在，用于文件留档
    files_archive_dir = 'files'
    os.makedirs(files_archive_dir, exist_ok=True)
    
    # Save uploaded file temporarily and archive it
    file_id = str(uuid.uuid4())
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"{file_id}.docx")
    file.save(temp_path)
    
    # 保存文件到留档目录
    archive_filename = f"{file_id}_{file.filename}"
    archive_path = os.path.join(files_archive_dir, archive_filename)
    shutil.copy2(temp_path, archive_path)
    logger.info(f"文件已留档: {archive_path}")
    
    def generate():
        try:
            # 发送开始事件
            yield "event: start\ndata: {\"message\": \"开始处理文档...\"}\n\n"
            logger.info(f"开始处理文档: {file.filename}")
            
            # Process document
            yield "event: progress\ndata: {\"message\": \"正在读取文档内容...\", \"progress\": 10}\n\n"
            logger.info(f"正在读取文档内容...")
            
            document_text = process_document(temp_path)
            
            # 发送文档处理完成事件
            doc_info = f"文档读取完成，共{len(document_text)}字符"
            yield f"event: progress\ndata: {{\"message\": \"{doc_info}\", \"progress\": 30}}\n\n"
            logger.info(f"{doc_info}")
            
            # Generate test cases using AI with streaming progress
            yield "event: progress\ndata: {\"message\": \"正在使用AI分析需求文档...\", \"progress\": 40}\n\n"
            logger.info(f"正在使用AI分析需求文档...")
            
            # 创建一个简单的进度收集器
            progress_messages = []
            
            def simple_progress_callback(message: str, progress: float = None):
                """简单的进度回调，收集进度信息"""
                progress_messages.append({
                    'message': message,
                    'progress': progress,
                    'timestamp': beijing_time()
                })
                logger.info(f"进度: {message} (进度: {progress}%)")
            
            # 使用带进度回调的函数
            yield "event: progress\ndata: {\"message\": \"AI分析进行中，正在生成测试点...\", \"progress\": 50}\n\n"
            
            result = generate_test_cases_with_progress(
                document_text=document_text,
                model_name=model_name,
                progress_callback=simple_progress_callback
            )
            
            # 发送分析完成事件
            total_points = len(result.get('test_points', []))
            total_cases = len(result.get('test_cases', []))
            model_used = result.get('model_used', '未知模型')
            completion_msg = f"AI分析完成，使用{model_used}生成{total_points}个测试点和{total_cases}个测试用例"
            yield f"event: progress\ndata: {{\"message\": \"{completion_msg}\", \"progress\": 90}}\n\n"
            logger.info(f"{completion_msg}")
            
            # Save to history
            history_id = history_manager.add_analysis(
                document_text=document_text,
                analysis_result=result,
                original_filename=file.filename,
                user_notes=None
            )
            
            # Add history ID to result
            result['history_id'] = history_id
            result['original_filename'] = file.filename
            result['processed_at'] = beijing_time()
            result['progress_messages'] = progress_messages  # 可选：包含进度消息
            
            # 发送进度100%事件
            yield f"event: progress\ndata: {json.dumps({'message': '分析完成，准备显示结果', 'progress': 100}, ensure_ascii=False)}\n\n"
            
            # 发送最终结果
            yield f"event: complete\ndata: {json.dumps(result, ensure_ascii=False)}\n\n"
            logger.info(f"分析完成，结果已发送到前端")
            
            # Clean up temp file
            os.remove(temp_path)
            logger.info(f"临时文件已清理: {temp_path}")
            
        except Exception as e:
            # 发送错误事件
            error_msg = str(e)
            logger.error(f"处理文档时出错: {error_msg}", exc_info=True)
            yield f"event: error\ndata: {{\"error\": \"{error_msg}\"}}\n\n"
            # Clean up temp file in case of error
            if os.path.exists(temp_path):
                os.remove(temp_path)
                logger.info(f"错误后清理临时文件: {temp_path}")
    
    return Response(generate(), mimetype="text/event-stream")

@app.route('/export/excel', methods=['POST'])
def export_excel():
    """
    导出分析结果为Excel文件
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # 生成Excel文件并返回字节流
        excel_bytes = export_to_excel_bytes(data)
        
        # 创建文件响应
        return send_file(
            BytesIO(excel_bytes),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'test_analysis_{str(uuid.uuid4())[:8]}.xlsx'
        )
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/history', methods=['GET', 'DELETE'])
def get_history():
    """
    获取历史记录列表或清空所有历史记录
    """
    if request.method == 'GET':
        try:
            history_list = history_manager.get_all_history()
            return jsonify(history_list)
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    elif request.method == 'DELETE':
        try:
            success = history_manager.clear_all_history()
            if not success:
                return jsonify({'error': 'Failed to clear history'}), 500
            return jsonify({'success': True})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@app.route('/history/<record_id>', methods=['GET'])
def get_history_record(record_id):
    """
    获取特定历史记录的详细信息
    """
    try:
        record = history_manager.get_history_by_id(record_id)
        if not record:
            return jsonify({'error': 'Record not found'}), 404
        
        return jsonify(record)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/history/delete/<record_id>', methods=['DELETE'])
def delete_history_record(record_id):
    """
    删除历史记录
    """
    try:
        success = history_manager.delete_history(record_id)
        if not success:
            return jsonify({'error': 'Record not found'}), 404
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/history/statistics', methods=['GET'])
def get_history_statistics():
    """
    获取历史统计信息
    """
    try:
        stats = history_manager.get_statistics()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    # 确保历史数据目录存在
    os.makedirs('history_data', exist_ok=True)
    app.run(host='0.0.0.0', port=18150, debug=True)
