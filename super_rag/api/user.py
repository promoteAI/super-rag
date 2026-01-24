from super_rag.db.models import User
# 默认User依赖，id固定为123
def default_user():
    return User(id="123")