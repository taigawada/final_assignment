import csv

def to_csv(csv_path: str, json_data, is_lucky: bool):
    log_append = open(csv_path, 'a')
    line_items = json_data["line_items"]
    append_csv = csv.writer(log_append)
    for index in range(len(line_items)):
        line_item = line_items[index]
        row = [
            json_data["name"], # 注文番号
            json_data["source_name"], #pos
            json_data["created_at"], #注文日時
            line_item["title"], #タイトル
            line_item["variant_title"], #バリエーション
            line_item["quantity"], #数量
            int(line_item["price"]), #値段
            int(line_item["total_discount"]), #値引き額
            (lambda index:int(json_data["total_price"]) if index==0 else '')(index), #小計
            (lambda index:int(json_data["total_discounts"]) if index==0 else '')(index), #割引
            (lambda index:int(json_data["total_price"])-int(json_data["total_discounts"]) if index==0 else '')(index), #合計
            is_lucky, #当たり
        ]
        append_csv.writerow(row)
    log_append.close()