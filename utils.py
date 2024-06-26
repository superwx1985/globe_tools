def little_endian_to_decimal(hex_str):
    # 移除空格并将其转换为字节数组
    hex_bytes = bytes.fromhex(hex_str.replace(' ', ''))
    # 将小端序字节数组转换为大端序
    big_endian_bytes = hex_bytes[::-1]
    # 将大端序字节数组转换为十六进制字符串
    big_endian_hex_str = big_endian_bytes.hex()
    # 将十六进制字符串转换为十进制整数
    decimal_value = int(big_endian_hex_str, 16)
    return decimal_value

if __name__ == '__main__':
    hex_str = '4e bb 02 0e'
    decimal_value = little_endian_to_decimal(hex_str)
    print(f'The decimal value of little-endian hex {hex_str} is {decimal_value}')