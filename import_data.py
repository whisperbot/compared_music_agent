import sqlite3
import csv
import sys

def import_csv(csv_path):
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    
    success_count = 0
    skip_count = 0
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 5:
                skip_count += 1
                continue
            vid, url1, url2, url3, url4 = row[:5]
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO videos (vid, url1, url2, url3, url4)
                    VALUES (?, ?, ?, ?, ?)
                ''', (vid.strip(), url1.strip(), url2.strip(), url3.strip(), url4.strip()))
                if cursor.rowcount > 0:
                    success_count += 1
                else:
                    skip_count += 1
            except Exception as e:
                print(f'导入失败 {vid}: {e}')
                skip_count += 1
    
    conn.commit()
    conn.close()
    print(f'导入完成！成功：{success_count} 条，跳过：{skip_count} 条')

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('使用方法: python import_data.py 你的视频CSV文件路径')
        print('CSV格式: vid,url1,url2,url3,url4')
        sys.exit(1)
    import_csv(sys.argv[1])
