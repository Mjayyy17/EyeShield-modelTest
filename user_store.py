from auth import UserManager as AuthUserManager

class UserStore:
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
                "availability_json": availability_json or "",
                "role": role,
                "is_active": bool(is_active),
            }
            for username, full_name, display_name, contact, specialization, availability_json, role, is_active in users
        ]

    @classmethod
    def save_users(cls, users):
        return users

    @staticmethod
    def _resolve_actor(acting_username=None, acting_role=None):
        return acting_username, acting_role

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
        availability_json="",
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
            availability_json=availability_json,
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
    def delete_user(cls, username, acting_username=None, acting_role=None, acting_password=None):
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
            acting_password=acting_password,
        )

    @classmethod
    def get_all_users(cls):
        return cls.load_users()

    @classmethod
    def reset_password(cls, username, new_password, acting_username=None, acting_role=None, acting_password=None):
        acting_username, acting_role = cls._resolve_actor(acting_username, acting_role)
        return AuthUserManager.reset_password(
            username,
            new_password,
            acting_username=acting_username,
            acting_role=acting_role,
            acting_password=acting_password,
        )

    @classmethod
    def update_user_role(cls, username, new_role, acting_username=None, acting_role=None, acting_password=None):
        acting_username, acting_role = cls._resolve_actor(acting_username, acting_role)
        return AuthUserManager.update_user_role(
            username,
            new_role,
            acting_username=acting_username,
            acting_role=acting_role,
            acting_password=acting_password,
        )

    @classmethod
    def update_user_availability(cls, username, availability_json, acting_username=None, acting_role=None, acting_password=None):
        acting_username, acting_role = cls._resolve_actor(acting_username, acting_role)
        return AuthUserManager.update_user_availability(
            username,
            availability_json,
            acting_username=acting_username,
            acting_role=acting_role,
            acting_password=acting_password,
        )

    @classmethod
    def update_user_active_status(cls, username, is_active, acting_username=None, acting_role=None, acting_password=None):
        acting_username, acting_role = cls._resolve_actor(acting_username, acting_role)
        return AuthUserManager.update_user_active_status(
            username,
            bool(is_active),
            acting_username=acting_username,
            acting_role=acting_role,
            acting_password=acting_password,
        )

    @classmethod
    def log_activity(cls, username, action, action_time=None):
        return AuthUserManager.add_activity_log(username, action, action_time)

    @classmethod
    def log_activity_event(cls, username, event_type, metadata=None, action_time=None, action_text=None):
        return AuthUserManager.add_activity_event(
            username=username,
            event_type=event_type,
            metadata=metadata,
            action_time=action_time,
            action_text=action_text,
        )

    @classmethod
    def get_activity_logs(
        cls,
        from_time=None,
        to_time=None,
        query=None,
        limit=100,
        offset=0,
        event_type=None,
        username=None,
        acting_username=None,
        acting_role=None,
    ):
        return AuthUserManager.get_activity_logs(
            from_time=from_time,
            to_time=to_time,
            query=query,
            limit=limit,
            offset=offset,
            event_type=event_type,
            username=username,
            acting_username=acting_username,
            acting_role=acting_role,
        )

    @classmethod
    def get_recent_activity(cls, limit=120, acting_username=None, acting_role=None):
        entries, _total = AuthUserManager.get_activity_logs(
            limit=limit,
            offset=0,
            acting_username=acting_username,
            acting_role=acting_role,
        )
        return entries

    @classmethod
    def update_own_account(cls, current_username, current_password, new_display_name, new_username=None, new_password=None):
        return AuthUserManager.update_own_account(
            current_username=current_username,
            current_password=current_password,
            new_display_name=new_display_name,
            new_username=new_username,
            new_password=new_password,
        )

    @classmethod
    def update_own_availability(cls, current_username, availability_json):
        return AuthUserManager.update_own_availability(
            current_username=current_username,
            availability_json=availability_json,
        )

    @classmethod
    def get_inactivity_policy(cls, username):
        return AuthUserManager.get_inactivity_policy(username)

    @classmethod
    def update_own_inactivity_timeout(cls, current_username, timeout_minutes):
        return AuthUserManager.update_own_inactivity_timeout(
            current_username=current_username,
            timeout_minutes=timeout_minutes,
        )

# For backward compatibility with existing code
load_users = UserStore.load_users
save_users = UserStore.save_users
add_user = UserStore.add_user
delete_user = UserStore.delete_user
get_all_users = UserStore.get_all_users
reset_password = UserStore.reset_password
update_user_role = UserStore.update_user_role
update_user_availability = UserStore.update_user_availability
update_user_active_status = UserStore.update_user_active_status
log_activity = UserStore.log_activity
log_activity_event = UserStore.log_activity_event
get_activity_logs = UserStore.get_activity_logs
get_recent_activity = UserStore.get_recent_activity
update_own_account = UserStore.update_own_account
update_own_availability = UserStore.update_own_availability
get_inactivity_policy = UserStore.get_inactivity_policy
update_own_inactivity_timeout = UserStore.update_own_inactivity_timeout
