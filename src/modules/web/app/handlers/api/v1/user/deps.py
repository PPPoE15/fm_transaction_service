from sqlalchemy.ext.asyncio import AsyncSession

from modules.web.app.application.queries.user.queries import TransactionQueries
from modules.web.logger import get_logger


def build_queries(session: AsyncSession) -> TransactionQueries:
    """
    Построить объект с запросами для сущности System User со всеми необходимыми зависимостями.

    Args:
        session: Сессия SQLAlchemy ORM.
        user_uid: Идентификатор пользователя.
    """
    return TransactionQueries(
        session=session,
        access_controller=None,
        logger=get_logger(),
    )


# def build_system_user_update_handler(user_uid: types.UserUID) -> SystemUserUpdateCommandHandler:
#     """
#     Построить обработчик обновления сущности пользователя.

#     Args:
#         user_uid: Идентификатор пользователя.
#     """
#     return SystemUserUpdateCommandHandler(
#         unit_of_work=SystemUsersUpdateHandlerUOW(
#             session_factory=handlers_deps.async_session_factory,
#             access_controller_builder=_system_user_access_controller_builder(user_uid),
#         ),
#     )


# def build_system_user_delete_handler(user_uid: types.UserUID) -> SystemUserDeleteCommandHandler:
#     """
#     Построить обработчик удаления сущности пользователя.

#     Args:
#         user_uid: Идентификатор пользователя.
#     """
#     rmq_producer = handlers_deps.build_rmq_producer()
#     return SystemUserDeleteCommandHandler(
#         unit_of_work=SystemUsersDeleteHandlerUOW(
#             session_factory=handlers_deps.async_session_factory,
#             access_controller_builder=_system_user_access_controller_builder(user_uid),
#         ),
#         rmq_adapter=MergedACLRMQAdapter(producer=rmq_producer),
#     )


# def build_system_user_include_permissions_handler(
#     user_uid: types.UserUID,
# ) -> SystemUserIncludePermissionsCommandHandler:
#     """
#     Построить обработчик добавления возможностей для сущности пользователя.

#     Args:
#         user_uid: Идентификатор пользователя.
#     """
#     rmq_producer = handlers_deps.build_rmq_producer()
#     return SystemUserIncludePermissionsCommandHandler(
#         unit_of_work=SystemUsersIncludePermissionsHandlerUOW(
#             session_factory=handlers_deps.async_session_factory,
#             access_controller_builder=_system_user_access_controller_builder(user_uid),
#         ),
#         rmq_adapter=MergedACLRMQAdapter(producer=rmq_producer),
#     )


# def build_system_user_exclude_permissions_handler(
#     user_uid: types.UserUID,
# ) -> SystemUserExcludePermissionsCommandHandler:
#     """
#     Построить обработчик исключения возможностей у сущности пользователя.

#     Args:
#         user_uid: Идентификатор пользователя.
#     """
#     rmq_producer = handlers_deps.build_rmq_producer()
#     return SystemUserExcludePermissionsCommandHandler(
#         unit_of_work=SystemUsersExcludePermissionsHandlerUOW(
#             session_factory=handlers_deps.async_session_factory,
#             access_controller_builder=_system_user_access_controller_builder(user_uid),
#         ),
#         rmq_adapter=MergedACLRMQAdapter(producer=rmq_producer),
#     )


# def build_system_user_link_scopes_handler(
#     user_uid: types.UserUID,
# ) -> SystemUserLinkScopesCommandHandler:
#     """
#     Построить обработчик назначения набора возможностей на пользователя.

#     Args:
#         user_uid: Идентификатор пользователя.
#     """
#     rmq_producer = handlers_deps.build_rmq_producer()
#     return SystemUserLinkScopesCommandHandler(
#         unit_of_work=SystemUsersLinkScopesHandlerUOW(
#             session_factory=handlers_deps.async_session_factory,
#             system_user_access_controller_builder=_system_user_access_controller_builder(user_uid),
#             permissions_scope_access_controller_builder=handlers_deps.permissions_scope_access_controller_builder(
#                 user_uid
#             ),
#         ),
#         rmq_adapter=MergedACLRMQAdapter(producer=rmq_producer),
#     )


# def build_system_user_unlink_scopes_handler(
#     user_uid: types.UserUID,
# ) -> SystemUserUnlinkScopesCommandHandler:
#     """
#     Построить обработчик отвязки набора возможностей от пользователя.

#     Args:
#         user_uid: Идентификатор пользователя.
#     """
#     rmq_producer = handlers_deps.build_rmq_producer()
#     return SystemUserUnlinkScopesCommandHandler(
#         unit_of_work=SystemUsersUnlinkScopesHandlerUOW(
#             session_factory=handlers_deps.async_session_factory,
#             system_user_access_controller_builder=_system_user_access_controller_builder(user_uid),
#             permissions_scope_access_controller_builder=handlers_deps.permissions_scope_access_controller_builder(
#                 user_uid
#             ),
#         ),
#         rmq_adapter=MergedACLRMQAdapter(producer=rmq_producer),
#     )


# def _system_user_access_controller_builder(
#     user_uid: types.UserUID,
# ) -> Callable[[AsyncSession], SystemUsersAccessController]:
#     """
#     Внешняя функция строителя контроллера Access Control List.

#     Возвращает функцию - строитель контроллера пользовательских возможностей
#     Args:
#         user_uid: Идентификатор пользователя.
#     """

#     def build(session: AsyncSession) -> SystemUsersAccessController:
#         """
#         Построить контроллер пользовательских возможностей с необходимыми зависимостями.

#         Args:
#             session: сессия SQLAlchemy ORM.
#         """
#         return SystemUsersAccessController(
#             merged_acl_repo=MergedACLRepo(session=session),
#             user_uid=user_uid,
#         )

#     return build
