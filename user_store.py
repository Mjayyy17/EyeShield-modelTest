import os

from auth import UserManager as AuthUserManager

class UserStore:
    USER_FILE = "users_data.json"

    @classmethod
    def load_users(cls):
        users = AuthUserManager.get_all_users()
        return [
            {
                "username": username,
                "full_name": full_name or username,
                "display_name": display_name or full_name or username,
                "contact": contact or "",
                "specialization": specialization or "",
                "role": role,
            }
            for username, full_name, display_name, contact, specialization, role in users
        ]

    @classmethod
    def save_users(cls, users):
        return users

    @staticmethod
    def _resolve_actor(acting_username=None, acting_role=None):
        return (
            acting_username or os.environ.get("EYESHIELD_CURRENT_USER"),
            acting_role or os.environ.get("EYESHIELD_CURRENT_ROLE"),
        )

    @classmethod
    def add_user(
        cls,
        username,
        password,
        role,
        full_name,
        display_name,
        contact,
        specialization,
        acting_username=None,
        acting_role=None,
        acting_password=None,
    ):
        acting_username, acting_role = cls._resolve_actor(acting_username, acting_role)
        return AuthUserManager.create_user(
            username,
            password,
            role,
            full_name=full_name,
            display_name=display_name,
            contact=contact,
            specialization=specialization,
            acting_username=acting_username,
            acting_role=acting_role,
            acting_password=acting_password,
        )

    @classmethod
    def _get_user_role(cls, username):
        users = cls.load_users()
        return next((user.get("role") for user in users if user.get("username") == username), None)

    @classmethod
    def _count_admins(cls):
        users = cls.load_users()
        return len([user for user in users if user.get("role") == "admin"])

    @classmethod
    def delete_user(cls, username, acting_username=None, acting_role=None):
        acting_username, acting_role = cls._resolve_actor(acting_username, acting_role)
        role = cls._get_user_role(username)
        if role is None:
            return False
        if role == "admin":
            current_username = acting_username
            if current_username and current_username != username:
                return False
            if cls._count_admins() <= 1:
                return False
        return AuthUserManager.delete_user(
            username,
            acting_username=acting_username,
            acting_role=acting_role,
        )

    @classmethod
    def get_all_users(cls):
        return cls.load_users()

    @classmethod
    def reset_password(cls, username, new_password, acting_username=None, acting_role=None):
        acting_username, acting_role = cls._resolve_actor(acting_username, acting_role)
        return AuthUserManager.reset_password(
            username,
            new_password,
            acting_username=acting_username,
            acting_role=acting_role,
        )

    @classmethod
    def update_user_role(cls, username, new_role, acting_username=None, acting_role=None):
        acting_username, acting_role = cls._resolve_actor(acting_username, acting_role)
        return AuthUserManager.update_user_role(
            username,
            new_role,
            acting_username=acting_username,
            acting_role=acting_role,
        )

# For backward compatibility with existing code
load_users = UserStore.load_users
save_users = UserStore.save_users
add_user = UserStore.add_user
delete_user = UserStore.delete_user
get_all_users = UserStore.get_all_users
reset_password = UserStore.reset_password
update_user_role = UserStore.update_user_role
