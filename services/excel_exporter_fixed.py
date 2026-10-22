import openpyxl
import json
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter
from typing import Dict, List, Any
import datetime
import io

def export_to_excel_bytes_complete(analysis_result: Dict[str, Any]) -> bytes:
    """
    将分析结果导出为Excel字节流，用于直接下载
    包含两个sheet："测试点"和"测试用例"
    
    Args:
        analysis_result: AI生成的分析结果
        
    Returns:
        Excel文件的字节流
    """
    try:
        # 创建内存中的Excel文件
        output = io.BytesIO()
        
        # 创建工作簿
        wb = openpyxl.Workbook()
        
        # 删除默认创建的工作表
        wb.remove(wb.active)
        
        # 1. 创建测试点工作表
        ws_test_points = wb.create_sheet("测试点")
        
        # 设置列宽
        column_widths = [15, 20, 40, 15, 40, 30]
        for i, width in enumerate(column_widths, start=1):
            ws_test_points.column_dimensions[get_column_letter(i)].width = width
        
        # 测试点表头
        test_point_headers = ["测试点ID", "类别", "描述", "优先级", "需求引用", "边界情况"]
        for col, header in enumerate(test_point_headers, start=1):
            cell = ws_test_points.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(fill_type="solid", fgColor="4472C4")
            cell.alignment = Alignment(horizontal="center", vertical="center")
        
        # 写入测试点数据
        test_points = analysis_result.get('test_points', [])
        for row_idx, test_point in enumerate(test_points, start=2):
            # 跳过非字典的测试点
            if not isinstance(test_point, dict):
                continue
            ws_test_points.cell(row=row_idx, column=1, value=test_point.get('id', ''))
            ws_test_points.cell(row=row_idx, column=2, value=test_point.get('category', ''))
            ws_test_points.cell(row=row_idx, column=3, value=test_point.get('description', ''))
            
            # 根据优先级设置颜色
            priority_cell = ws_test_points.cell(row=row_idx, column=4, value=test_point.get('priority', '').upper())
            priority = test_point.get('priority', '').lower()
            if priority == 'critical':
                priority_cell.fill = PatternFill(fill_type="solid", fgColor="FF0000")
                priority_cell.font = Font(color="FFFFFF", bold=True)
            elif priority == 'high':
                priority_cell.fill = PatternFill(fill_type="solid", fgColor="FFC000")
            elif priority == 'medium':
                priority_cell.fill = PatternFill(fill_type="solid", fgColor="FFFF00")
            elif priority == 'low':
                priority_cell.fill = PatternFill(fill_type="solid", fgColor="92D050")
            
            ws_test_points.cell(row=row_idx, column=5, value=test_point.get('requirements_ref', ''))
            
            # 合并边界情况为字符串
            edge_cases = test_point.get('edge_cases', [])
            edge_cases_str = "\n".join(edge_cases)
            ws_test_points.cell(row=row_idx, column=6, value=edge_cases_str)
            ws_test_points.cell(row=row_idx, column=6).alignment = Alignment(wrap_text=True)
        
        # 2. 创建测试用例工作表
        ws_test_cases = wb.create_sheet("测试用例")
        
        # 设置列宽
        test_case_widths = [15, 15, 40, 30, 50, 40, 30]
        for i, width in enumerate(test_case_widths, start=1):
            ws_test_cases.column_dimensions[get_column_letter(i)].width = width
        
        # 测试用例表头
        test_case_headers = ["用例ID", "关联测试点", "标题", "前置条件", "测试步骤", "预期结果", "测试数据"]
        for col, header in enumerate(test_case_headers, start=1):
            cell = ws_test_cases.cell(row=1, column=col, value=header)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(fill_type="solid", fgColor="ED7D31")
            cell.alignment = Alignment(horizontal="center", vertical="center")
        
        # 写入测试用例数据
        test_cases = analysis_result.get('test_cases', [])
        for row_idx, test_case in enumerate(test_cases, start=2):
            # 跳过非字典的测试用例
            if not isinstance(test_case, dict):
                continue
            ws_test_cases.cell(row=row_idx, column=1, value=test_case.get('test_case_id', ''))
            ws_test_cases.cell(row=row_idx, column=2, value=test_case.get('linked_point_id', ''))
            ws_test_cases.cell(row=row_idx, column=3, value=test_case.get('title', ''))
            
            # 前置条件（移除序号，直接使用原始字符串）
            preconditions = test_case.get('preconditions', [])
            if isinstance(preconditions, list):
                # 直接使用原始字符串，不添加序号
                preconditions_str = "\n".join(preconditions)
            else:
                preconditions_str = str(preconditions)
            ws_test_cases.cell(row=row_idx, column=4, value=preconditions_str)
            ws_test_cases.cell(row=row_idx, column=4).alignment = Alignment(wrap_text=True)
            
            # 测试步骤（移除序号，直接使用原始字符串）
            steps = test_case.get('steps', [])
            if isinstance(steps, list):
                # 直接使用原始字符串，不添加序号
                steps_str = "\n".join(steps)
            else:
                steps_str = str(steps)
            ws_test_cases.cell(row=row_idx, column=5, value=steps_str)
            ws_test_cases.cell(row=row_idx, column=5).alignment = Alignment(wrap_text=True)
            
            # 预期结果 - 安全处理各种类型
            expected_result_val = test_case.get('expected_result', '')
            if isinstance(expected_result_val, list):
                expected_result_str = "\n".join(expected_result_val)
            else:
                expected_result_str = str(expected_result_val) if expected_result_val is not None else ''
            ws_test_cases.cell(row=row_idx, column=6, value=expected_result_str)
            ws_test_cases.cell(row=row_idx, column=6).alignment = Alignment(wrap_text=True)
            
            # 测试数据 - 安全处理各种类型
            test_data_val = test_case.get('test_data', '无')
            if test_data_val is None:
                test_data_val = '无'
            
            # 如果 test_data 是字典或列表，转换为格式化的 JSON 字符串
            if isinstance(test_data_val, (dict, list)):
                try:
                    test_data_val = json.dumps(test_data_val, ensure_ascii=False, indent=2)
                except:
                    test_data_val = str(test_data_val)
            else:
                test_data_val = str(test_data_val)
                
            ws_test_cases.cell(row=row_idx, column=7, value=test_data_val)
            ws_test_cases.cell(row=row_idx, column=7).alignment = Alignment(wrap_text=True)
        
        # 保存到字节流
        wb.save(output)
        output.seek(0)
        
        return output.getvalue()
    
    except Exception as e:
        # 如果生成Excel失败，抛出错误
        raise Exception(f"导出Excel失败: {str(e)}")

def export_to_excel_bytes_simple(analysis_result: Dict[str, Any]) -> bytes:
    """
    将分析结果导出为简化的Excel字节流，作为后备方案
    
    Args:
        analysis_result: AI生成的分析结果
        
    Returns:
        Excel文件的字节流
    """
    import io
    
    # 创建内存中的Excel文件
    output = io.BytesIO()
    
    # 创建工作簿
    wb = openpyxl.Workbook()
    
    # 简化版本，只创建必要的工作表
    ws_summary = wb.active
    ws_summary.title = "摘要"
    
    # 写入基本摘要
    ws_summary['A1'] = "测试分析报告"
    ws_summary['A1'].font = Font(size=14, bold=True)
    ws_summary['A2'] = f"生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    ws_summary['A3'] = f"测试点: {analysis_result.get('document_summary', {}).get('total_test_points', 0)}"
    ws_summary['A4'] = f"测试用例: {analysis_result.get('document_summary', {}).get('total_test_cases', 0)}"
    
    # 如果有测试点，添加测试点信息
    test_points = analysis_result.get('test_points', [])
    if test_points:
        ws_summary['A6'] = "测试点列表"
        ws_summary['A6'].font = Font(bold=True)
        
        # 写入表头
        headers = ["测试点ID", "类别", "描述", "优先级"]
        for col, header in enumerate(headers, start=1):
            cell = ws_summary.cell(row=7, column=col, value=header)
            cell.font = Font(bold=True)
        
        # 写入数据
        for row_idx, test_point in enumerate(test_points, start=8):
            ws_summary.cell(row=row_idx, column=1, value=test_point.get('id', ''))
            ws_summary.cell(row=row_idx, column=2, value=test_point.get('category', ''))
            ws_summary.cell(row=row_idx, column=3, value=test_point.get('description', ''))
            ws_summary.cell(row=row_idx, column=4, value=test_point.get('priority', '').upper())
    
    # 保存到字节流
    wb.save(output)
    output.seek(0)
    
    return output.getvalue()

# 为了兼容性，保留原有函数名
export_to_excel_bytes = export_to_excel_bytes_complete

if __name__ == "__main__":
    # 测试代码
    sample_result = {
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
    
    try:
        excel_bytes = export_to_excel_bytes_complete(sample_result)
        print(f"Excel字节流生成成功，大小: {len(excel_bytes)} 字节")
        
        # 保存到文件以便验证
        with open("test_complete_export.xlsx", "wb") as f:
            f.write(excel_bytes)
        print("测试文件已保存为 test_complete_export.xlsx")
    except Exception as e:
        print(f"导出失败: {e}")
