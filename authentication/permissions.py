from rest_framework import permissions

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        # so we'll always allow GET, HEAD or OPTIONS requests.
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to the owner of the object.
        return obj.user == request.user

class IsVendor(permissions.BasePermission):
    """
    Custom permission to only allow vendors.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == 'vendor'

class IsDriver(permissions.BasePermission):
    """
    Custom permission to only allow drivers.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == 'driver'

class IsCustomer(permissions.BasePermission):
    """
    Custom permission to only allow customers.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type == 'customer'

class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow admins to edit, others can read.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated and request.user.user_type == 'admin'
