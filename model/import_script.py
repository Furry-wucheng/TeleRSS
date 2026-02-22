import asyncio
from model.follower_model import add_new_follower

"""
这是一个从txt文件导入到数据库的脚本文件
第一个为id，第二个是分类
"""

async def main():
    ids = set()
    tasks = []
    with open("../follower.txt", "r", encoding="utf-8") as file:
        for line in file.readlines():
            line = line.strip()
            if line == "":
                continue
            if " " not in line:
                if line in ids:
                    raise ValueError(f"id 重复:{line}")
                ids.add(line)
                tasks.append(add_new_follower(line))
            else:
                user_id, category = line.split(" ", 1)
                if category == "" or user_id == "":
                    raise ValueError("category 不能为空")
                if user_id in ids:
                    raise ValueError(f"id 重复:{user_id}")
                ids.add(user_id)
                tasks.append(add_new_follower(user_id, category))

    await asyncio.gather(*tasks)
    print(f"导入完成，共 {len(tasks)} 条记录。")


if __name__ == "__main__":
    asyncio.run(main())
