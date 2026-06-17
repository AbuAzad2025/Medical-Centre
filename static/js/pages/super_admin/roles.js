function editRole(roleId) {
            window.location.href = `/super-admin/roles/${roleId}/edit`;
        }
        
        function managePermissions(roleId) {
            window.location.href = `/super-admin/roles/${roleId}/permissions`;
        }

        function manageDepartmentPermissions(roleId) {
            window.location.href = `/super-admin/roles/${roleId}/department-permissions`;
        }
