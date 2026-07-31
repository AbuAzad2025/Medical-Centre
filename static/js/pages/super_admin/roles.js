function editRole(roleId) {
            window.location.href = (window.API_ROUTES && window.API_ROUTES.edit_role) ? window.API_ROUTES.edit_role.replace('/0', '/' + roleId) : `/super-admin/roles/${roleId}/edit`;
        }
        
        function managePermissions(roleId) {
            window.location.href = (window.API_ROUTES && window.API_ROUTES.manage_role_permissions) ? window.API_ROUTES.manage_role_permissions.replace('/0', '/' + roleId) : `/super-admin/roles/${roleId}/permissions`;
        }

        function manageDepartmentPermissions(roleId) {
            window.location.href = (window.API_ROUTES && window.API_ROUTES.manage_role_department_permissions) ? window.API_ROUTES.manage_role_department_permissions.replace('/0', '/' + roleId) : `/super-admin/roles/${roleId}/department-permissions`;
        }
