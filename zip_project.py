import os
import zipfile
from pathlib import Path

# ==================== 超参数区 ====================
SOURCE_DIR = "td3e3nn"           # 要打包的源目录
OUTPUT_ZIP = "td3e3nn.zip"       # 输出zip文件名
EXCLUDE_DIRS = ["outputs", ".venv"]  # 要排除的一级目录列表
# =================================================

def get_dir_size(path):
    """计算目录总大小（字节）"""
    total = 0
    for dirpath, dirnames, filenames in os.walk(path):
        # 排除指定目录
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.exists(fp):
                total += os.path.getsize(fp)
    return total

def format_size(size_bytes):
    """格式化文件大小显示"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

def preview_zip_contents(source_dir, exclude_dirs):
    """预览将要打包的内容"""
    source_path = Path(source_dir)
    if not source_path.exists():
        print(f"❌ 错误：目录 '{source_dir}' 不存在！")
        return None, []
    
    included_files = []
    total_size = 0
    excluded_dirs_found = []
    
    print(f"\n📁 源目录: {os.path.abspath(source_dir)}")
    print(f"🚫 排除目录: {exclude_dirs}")
    print("\n" + "="*50)
    print("📋 扫描中...\n")
    
    # 检查一级目录中的排除项
    for item in source_path.iterdir():
        if item.is_dir() and item.name in exclude_dirs:
            excluded_dirs_found.append(item.name)
            excluded_size = get_dir_size(str(item))
            print(f"  ⛔ [排除] {item.name}/ ({format_size(excluded_size)})")
    
    print("\n" + "-"*50)
    print("✅ 将包含的文件（前20个示例）：\n")
    
    count = 0
    for root, dirs, files in os.walk(source_dir):
        # 相对路径
        rel_root = os.path.relpath(root, source_dir)
        
        # 排除指定的一级目录
        if rel_root == '.':
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
        else:
            # 检查是否在排除目录的子目录中
            top_dir = rel_root.split(os.sep)[0]
            if top_dir in exclude_dirs:
                dirs[:] = []
                continue
        
        for file in files:
            file_path = os.path.join(root, file)
            arcname = os.path.relpath(file_path, source_dir)
            file_size = os.path.getsize(file_path)
            
            included_files.append((file_path, arcname, file_size))
            total_size += file_size
            
            if count < 20:
                print(f"  + {arcname} ({format_size(file_size)})")
                count += 1
            elif count == 20:
                print(f"  ... 还有 {len(files) - 20} 个文件 ...")
                count += 1
    
    total_files = len(included_files)
    print(f"\n" + "="*50)
    print(f"📊 统计信息:")
    print(f"   总文件数: {total_files}")
    print(f"   预估大小: {format_size(total_size)}")
    print(f"   排除目录: {excluded_dirs_found}")
    print(f"   输出文件: {OUTPUT_ZIP}")
    
    return total_size, included_files

def create_zip(source_dir, output_zip, exclude_dirs, file_list):
    """创建zip文件"""
    print(f"\n🗜️  正在创建 {output_zip} ...")
    
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path, arcname, _ in file_list:
            zipf.write(file_path, arcname)
    
    final_size = os.path.getsize(output_zip)
    print(f"✅ 完成！")
    print(f"   ZIP文件大小: {format_size(final_size)}")
    print(f"   压缩率: {(1 - final_size/get_dir_size(source_dir))*100:.1f}%")

# ==================== 执行流程 ====================
print("🔍 第一步：扫描并预估大小...")
estimated_size, files_to_zip = preview_zip_contents(SOURCE_DIR, EXCLUDE_DIRS)

if files_to_zip:
    print("\n" + "="*50)
    user_input = input("\n💡 是否确认打包？ (y/n): ").strip().lower()
    
    if user_input == 'y':
        create_zip(SOURCE_DIR, OUTPUT_ZIP, EXCLUDE_DIRS, files_to_zip)
    else:
        print("❌ 已取消打包操作")
else:
    print("\n⚠️ 没有找到可打包的文件")