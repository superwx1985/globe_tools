import csv
from datetime import datetime, timedelta
from pymongo import MongoClient


# 配置MongoDB连接
client = MongoClient("mongodb://52.82.80.187:27017/")
db = client["DataV"]
collection = db["vehicle_data"]


def process_csv_and_update_db(csv_file_path, mac=None, day_offset=0, batch_size=1000):
    """
    读取CSV文件，修改指定数据，并插入到MongoDB。

    :param csv_file_path: CSV文件路径
    :param day_offset: 偏移的天数，整数（正为增加天数，负为减少天数）
    """
    try:
        documents = []
        with open(csv_file_path, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                # 获取并修改数据
                created_time = datetime.strptime(row['created'], "%Y-%m-%d %H:%M:%S")
                new_created_time = created_time + timedelta(days=day_offset)

                value_parts = row['value'].split(',')
                if len(value_parts) == 4:
                    value_parts[0] = new_created_time.strftime("%Y%m%d%H%M%S")
                    value_parts[3] = new_created_time.strftime("%Y%m%d%H%M%S")

                new_value = ','.join(value_parts)

                # 构造要插入的文档
                document = {
                    "timestamp": new_created_time,
                    "metadata": {
                        "index": int(row['index']),
                        "mac": mac if mac else row['mac']
                    },
                    "val": new_value
                }
                documents.append(document)

                # 批量插入
                if len(documents) >= batch_size:
                    collection.insert_many(documents)
                    print(f"已插入{len(documents)}条文档")
                    documents = []

            # 插入剩余文档
            if documents:
                collection.insert_many(documents)
                print(f"已插入{len(documents)}条文档")
    except Exception as e:
        print(f"处理CSV文件时出错: {e}")


if __name__ == '__main__':
    csv_file_path = r"D:\ShareCache\王歆\working\task\dataV\stihl 真车数据 956002678-0922-1006.csv"  # 替换为你的CSV文件路径
    mac = "87654321F641"
    day_offset = 69  # 替换为你的目标偏移天数
    process_csv_and_update_db(csv_file_path, mac, day_offset)
