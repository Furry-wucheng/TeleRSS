from model import get_session,FollowerTable

"""
这是一个从txt文件导入到数据库的脚本文件
第一个为id，第二个是分类
"""
ids = set()
session = get_session()
with open("../follower.txt","r",encoding="utf-8") as file:
    for line in file.readlines():
        line = line.strip()
        if line == "":
            continue
        if " " not in line:
            if line in ids:
                raise ValueError(f"id 重复:{line}")
            ids.add( line)
            session.add(FollowerTable(user_id=line))
        else:
            user_id, category = line.split(" ")
            if category == "" or user_id == "":
                raise ValueError("category 不能为空")
            if user_id in ids:
                raise ValueError(f"id 重复:{user_id}")
            ids.add(user_id)
            session.add(FollowerTable(user_id=user_id,category=category))

session.commit()

