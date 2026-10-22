import json
import os
import uuid
from typing import Dict, List, Any, Optional
import datetime

class HistoryManager:
    """
    历史数据管理器，用于存储和检索分析历史
    """
    
    def __init__(self, storage_path: str = "history_data"):
        """
        初始化历史管理器
        
        Args:
            storage_path: 历史数据存储目录
        """
        self.storage_path = storage_path
        self.history_file = os.path.join(storage_path, "history.json")
        
        # 确保存储目录存在
        os.makedirs(storage_path, exist_ok=True)
        
        # 初始化历史记录
        self.history = self._load_history()
    
    def _load_history(self) -> List[Dict[str, Any]]:
        """
        从文件加载历史记录
        
        Returns:
            历史记录列表
        """
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载历史记录失败: {e}")
                return []
        return []
    
    def _save_history(self):
        """保存历史记录到文件"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存历史记录失败: {e}")
    
    def add_analysis(
        self, 
        document_text: str, 
        analysis_result: Dict[str, Any],
        original_filename: str = None,
        user_notes: str = None
    ) -> str:
        """
        添加新的分析记录
        
        Args:
            document_text: 原始文档文本
            analysis_result: 分析结果
            original_filename: 原始文件名
            user_notes: 用户备注
            
        Returns:
            记录ID
        """
        record_id = str(uuid.uuid4())
        timestamp = datetime.datetime.now().isoformat()
        
        # 创建简洁的摘要信息
        summary = {
            "total_test_points": analysis_result.get('document_summary', {}).get('total_test_points', 0),
            "total_test_cases": analysis_result.get('document_summary', {}).get('total_test_cases', 0),
            "total_characters": analysis_result.get('document_summary', {}).get('total_characters', 0)
        }
        
        # 优先级统计
        priority_stats = analysis_result.get('analysis_summary', {})
        
        # 提取前几个测试点作为预览
        test_points_preview = []
        for test_point in analysis_result.get('test_points', [])[:3]:  # 只取前3个
            test_points_preview.append({
                "id": test_point.get('id'),
                "category": test_point.get('category'),
                "description": test_point.get('description'),
                "priority": test_point.get('priority')
            })
        
        record = {
            "id": record_id,
            "timestamp": timestamp,
            "original_filename": original_filename,
            "user_notes": user_notes,
            "summary": summary,
            "priority_stats": priority_stats,
            "test_points_preview": test_points_preview,
            "full_result_path": os.path.join(self.storage_path, f"{record_id}.json")
        }
        
        # 保存完整结果到单独文件
        full_result = {
            "metadata": {
                "id": record_id,
                "timestamp": timestamp,
                "original_filename": original_filename,
                "user_notes": user_notes
            },
            "document_text": document_text,
            "analysis_result": analysis_result
        }
        
        try:
            with open(record["full_result_path"], 'w', encoding='utf-8') as f:
                json.dump(full_result, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存完整结果失败: {e}")
            # 如果保存失败，仍然创建记录但不包含完整结果路径
            record["full_result_path"] = None
        
        # 添加到历史记录
        self.history.append(record)
        
        # 只保留最近的100条记录
        if len(self.history) > 100:
            # 删除最旧的记录及其对应的文件
            old_record = self.history.pop(0)
            if old_record.get("full_result_path") and os.path.exists(old_record["full_result_path"]):
                try:
                    os.remove(old_record["full_result_path"])
                except:
                    pass
        
        # 保存历史索引
        self._save_history()
        
        return record_id
    
    def get_all_history(self) -> List[Dict[str, Any]]:
        """
        获取所有历史记录（简略信息）
        
        Returns:
            历史记录列表（不包含完整分析结果）
        """
        # 按时间倒序排序
        sorted_history = sorted(self.history, key=lambda x: x.get('timestamp', ''), reverse=True)
        return sorted_history
    
    def get_history_by_id(self, record_id: str) -> Optional[Dict[str, Any]]:
        """
        根据ID获取完整的历史记录
        
        Args:
            record_id: 记录ID
            
        Returns:
            完整的历史记录，包含文档文本和分析结果
        """
        # 首先在索引中查找
        record_info = None
        for record in self.history:
            if record.get('id') == record_id:
                record_info = record
                break
        
        if not record_info:
            return None
        
        # 尝试加载完整结果
        full_result_path = record_info.get('full_result_path')
        if full_result_path and os.path.exists(full_result_path):
            try:
                with open(full_result_path, 'r', encoding='utf-8') as f:
                    full_result = json.load(f)
                return full_result
            except Exception as e:
                print(f"加载完整结果失败: {e}")
        
        return None
    
    def delete_history(self, record_id: str) -> bool:
        """
        删除历史记录
        
        Args:
            record_id: 记录ID
            
        Returns:
            是否删除成功
        """
        # 查找记录
        record_index = -1
        record_info = None
        
        for i, record in enumerate(self.history):
            if record.get('id') == record_id:
                record_index = i
                record_info = record
                break
        
        if record_index == -1:
            return False
        
        # 删除对应的文件
        if record_info and record_info.get('full_result_path'):
            try:
                if os.path.exists(record_info['full_result_path']):
                    os.remove(record_info['full_result_path'])
            except:
                pass
        
        # 从历史记录中删除
        self.history.pop(record_index)
        self._save_history()
        
        return True
    
    def clear_all_history(self) -> bool:
        """
        清除所有历史记录
        
        Returns:
            是否清除成功
        """
        try:
            # 删除所有结果文件
            for record in self.history:
                if record.get('full_result_path') and os.path.exists(record['full_result_path']):
                    try:
                        os.remove(record['full_result_path'])
                    except:
                        pass
            
            # 清空历史记录
            self.history = []
            self._save_history()
            
            return True
        except Exception as e:
            print(f"清除历史记录失败: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取历史统计信息
        
        Returns:
            统计信息
        """
        total_records = len(self.history)
        
        if total_records == 0:
            return {
                "total_records": 0,
                "total_test_points": 0,
                "total_test_cases": 0,
                "average_test_points": 0,
                "average_test_cases": 0
            }
        
        total_test_points = 0
        total_test_cases = 0
        
        for record in self.history:
            total_test_points += record.get('summary', {}).get('total_test_points', 0)
            total_test_cases += record.get('summary', {}).get('total_test_cases', 0)
        
        return {
            "total_records": total_records,
            "total_test_points": total_test_points,
            "total_test_cases": total_test_cases,
            "average_test_points": total_test_points / total_records,
            "average_test_cases": total_test_cases / total_records
        }

# 全局历史管理器实例
history_manager = HistoryManager()

if __name__ == "__main__":
    # 测试代码
    manager = HistoryManager("test_history")
    
    # 添加测试记录
    test_result = {
        "document_summary": {
            "total_characters": 1500,
            "total_test_points": 5,
            "total_test_cases": 15
        },
        "test_points": [
            {
                "id": "TP-001",
                "category": "认证",
                "description": "用户登录功能测试",
                "priority": "critical",
                "requirements_ref": "用户应能够使用用户名和密码登录",
                "edge_cases": ["空用户名", "空密码", "错误凭证"]
            }
        ],
        "test_cases": [
            {
                "test_case_id": "TC-001",
                "linked_point_id": "TP-001",
                "title": "正常登录测试",
                "preconditions": ["系统正常运行", "用户账户存在"],
                "steps": ["打开登录页面", "输入有效用户名", "输入有效密码", "点击登录按钮"],
                "expected_result": "登录成功，跳转到主页",
                "test_data": "用户名: testuser, 密码: Test123!"
            }
        ],
        "analysis_summary": {
            "critical_count": 2,
            "high_count": 1,
            "medium_count": 1,
            "low_count": 1
        }
    }
    
    record_id = manager.add_analysis(
        document_text="测试文档内容",
        analysis_result=test_result,
        original_filename="test_requirements.docx",
        user_notes="测试备注"
    )
    
    print(f"添加记录成功，ID: {record_id}")
    
    # 获取所有历史
    all_history = manager.get_all_history()
    print(f"历史记录数量: {len(all_history)}")
    
    # 获取统计信息
    stats = manager.get_statistics()
    print(f"统计信息: {stats}")
    
    # 获取单个记录
    single_record = manager.get_history_by_id(record_id)
    if single_record:
        print(f"获取记录成功，文档长度: {len(single_record.get('document_text', ''))}")
    
    # 清理测试数据
    import shutil
    if os.path.exists("test_history"):
        shutil.rmtree("test_history")
