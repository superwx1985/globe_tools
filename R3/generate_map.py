import json
import math
import os
import copy
import time
from pprint import pprint
from pathlib import Path
from jsonpath_ng import parse, Fields, Index


def generate_point_list(center_x, center_y, target_area, n_points):
    target_radius = math.sqrt(target_area / math.pi)
    circle_points = []

    # 生成角度序列（0到2π）
    angle_step = 2 * math.pi / n_points
    for i in range(n_points):
        angle = i * angle_step
        x = center_x + target_radius * math.cos(angle)
        y = center_y + target_radius * math.sin(angle)
        circle_points.append({"x": x, "y": y})

    return circle_points


def modify_json(json_data, json_path, value):
    try:
        jsonpath_expr = parse(json_path)
    except Exception as e:
        raise ValueError(f"无效的JSON Path表达式: {json_path}") from e

    # 创建深拷贝以避免修改原始数据
    modified_data = copy.deepcopy(json_data)

    matches = jsonpath_expr.find(modified_data)
    if not matches:
        raise ValueError(f"在JSON中未找到路径: {json_path}")

    # 处理第一个匹配项
    match = matches[0]

    # 获取父对象
    parent = match.context.value

    # 根据路径类型处理不同的访问方式
    if isinstance(match.path, Fields):
        # 对象字段访问
        field_name = match.path.fields[0]  # 取第一个字段名
        parent[field_name] = value
    elif hasattr(match.path, 'right'):
        # 复合路径（如数组索引或嵌套对象）
        last_accessor = match.path.right

        if isinstance(last_accessor, Index):
            # 数组索引访问
            parent[last_accessor.index] = value
        elif hasattr(last_accessor, 'value'):
            # 对象键访问
            parent[last_accessor.value] = value
        else:
            # 其他类型的访问器
            raise TypeError(f"不支持的访问器类型: {type(last_accessor).__name__}")
    elif match.context is None:
        # 匹配的是根节点
        return value
    else:
        # 其他类型的路径
        raise TypeError(f"不支持的路径类型: {type(match.path).__name__}")

    return modified_data


def replace_points_in_template(input_folder, output_folder, old_name, new_name, new_points):
    with open(os.path.join(input_folder, f"{old_name}.object"), 'r') as file:
        data = json.load(file)

    data = modify_json(data, "$.area.points", new_points)
    data = modify_json(data, "$.header.name", new_name)

    with open(os.path.join(output_folder, f"{new_name}.object"), 'w') as file:
        json.dump(data, file, indent=2)

    return data


def offset_points_in_template(input_folder, output_folder, old_name, new_name, offset_x=0, offset_y=0):
    with open(os.path.join(input_folder, f"{old_name}.object"), 'r') as file:
        data = json.load(file)

    object_type = parse("$.header.type.type").find(data)[0].value
    if object_type in [1, 3]:
        new_points = data['area']['points']
        print(new_points)
        for point in new_points:
            point['x'] = point['x'] + offset_x
            point['y'] = point['y'] + offset_y
        print(new_points)
        data = modify_json(data, "$.area.points", new_points)

    elif object_type == 4:
        new_points = data['transport_path']['points']
        print(new_points)
        for point in new_points:
            point['x'] = point['x'] + offset_x
            point['y'] = point['y'] + offset_y
        print(new_points)
        data = modify_json(data, "$.area.points", new_points)

    elif object_type in [5, 6]:
        point = data['waypoint']['location']
        print(point)
        point['x'] = point['x'] + offset_x
        point['y'] = point['y'] + offset_y
        print(point)
        data = modify_json(data, "$.waypoint.location", point)

    data = modify_json(data, "$.header.name", new_name)

    with open(os.path.join(output_folder, f"{new_name}.object"), 'w') as file:
        json.dump(data, file, indent=2)

    return data


def copy_zones(input_folder, output_folder, map_name, offset_x, offset_y):
    with open(os.path.join(input_folder, f"{map_name}.map"), 'r') as file:
        map_data = json.load(file)
    zones = map_data['objects']
    new_zones = []
    for zone in zones:
        old_zone_name = zone['name']
        x = f"D{abs(offset_x)}" if offset_x < 0 else f"{offset_x}"
        y = f"D{abs(offset_y)}" if offset_y < 0 else f"{offset_y}"
        new_zone_name = f"{old_zone_name}x{x}y{y}"
        print(f"Copying {old_zone_name} to {new_zone_name}")
        offset_points_in_template(input_folder, output_folder, old_zone_name, new_zone_name, offset_x, offset_y)
        new_zones.append({'cut': True, 'enabled': True, 'name': new_zone_name})

    if os.path.exists(os.path.join(output_folder, f"{map_name}.map")):
        with open(os.path.join(output_folder, f"{map_name}.map"), 'r') as file:
            map_data2 = json.load(file)
        zones2 = map_data2['objects']
        zones = zones2 + new_zones
    else:
        zones = zones + new_zones

    map_data = modify_json(map_data, "$.objects", zones)
    map_data = modify_json(map_data, "$.last_modification", int(time.time()))

    with open(os.path.join(output_folder, f"{map_name}.map"), 'w') as file:
            json.dump(map_data, file, indent=2)

    with open(os.path.join(input_folder, "definition.json"), 'r') as file:
        site_data = json.load(file)
    site_data = modify_json(site_data, "$.time_stamp", int(time.time()))
    with open(os.path.join(output_folder, "definition.json"), 'w') as file:
        json.dump(site_data, file, indent=2)


if __name__ == '__main__':
    input_folder = "template/bigGorson"
    output_folder = "template/newGorson"
    old_name = "gorsonbigMZ001"
    new_name = "gorsonbigMZ011"

    # 中心点（相对RA偏移多少米）
    center_x = 50
    center_y = 50
    # 面积（平方米）
    target_area = 1000
    # 生成多少个点组成的圆形
    n_points = 1000
    circle_points = generate_point_list(center_x, center_y, target_area, n_points)

    # result = replace_points_in_template(input_folder, output_folder, old_name, new_name, circle_points)

    # result = offset_points_in_template(input_folder, output_folder, old_name, new_name, 0, -100)
    #
    # pprint(result, indent=2, width=50)

    copy_zones(input_folder, output_folder, "gorsonMap001", 200, 100)
