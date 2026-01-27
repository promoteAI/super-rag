from super_rag.db.models import User, Role
# 默认User依赖
def default_user():
    return User(id="public", username="public", email="public@public.com", role=Role.ADMIN)