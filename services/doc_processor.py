import docx
import re
from typing import Optional

def process_document(file_path: str) -> str:
    """
    读取 .docx 文档并提取清洗后的文本内容
    
    Args:
        file_path: .docx 文件的路径
        
    Returns:
        清洗后的纯文本内容
        
    Raises:
        FileNotFoundError: 如果文件不存在
        ValueError: 如果文件不是有效的 .docx 文档
    """
    try:
        # 使用 python-docx 读取文档
        doc = docx.Document(file_path)
        
        # 提取所有段落文本
        paragraphs = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
        
        # 提取表格中的文本
        tables_text = []
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    cell_text = cell.text.strip()
                    if cell_text:
                        tables_text.append(cell_text)
        
        # 合并所有文本
        all_text = paragraphs + tables_text
        
        if not all_text:
            raise ValueError("Document appears to be empty")
        
        # 合并文本并清洗
        full_text = "\n".join(all_text)
        
        # 清洗步骤
        cleaned_text = clean_text(full_text)
        
        return cleaned_text
    
    except docx.opc.exceptions.PackageNotFoundError:
        raise ValueError("File is not a valid .docx document")
    except Exception as e:
        raise Exception(f"Error processing document: {str(e)}")

def clean_text(text: str) -> str:
    """
    清洗文本内容
    
    Args:
        text: 原始文本
        
    Returns:
        清洗后的文本
    """
    # 移除多余的换行符和空格
    text = re.sub(r'\n\s*\n', '\n\n', text)
    
    # 移除连续多个空格
    text = re.sub(r'[ \t]{2,}', ' ', text)
    
    # 移除特殊字符但保留中文、英文、数字和基本标点
    text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s,.，。!?；：;:\-_\'"()（）\[\]{}]', '', text)
    
    # 标准化段落分隔
    text = re.sub(r'([.!?。！？])\s*', r'\1\n', text)
    
    # 移除行首尾空格
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join([line for line in lines if line])
    
    return text

if __name__ == "__main__":
    # 测试代码
    import sys
    if len(sys.argv) > 1:
        result = process_document(sys.argv[1])
        print("Processed text:")
        print("=" * 50)
        print(result[:500] + "..." if len(result) > 500 else result)
        print("=" * 50)
        print(f"Total characters: {len(result)}")
    else:
        print("Usage: python doc_processor.py <file_path.docx>")
