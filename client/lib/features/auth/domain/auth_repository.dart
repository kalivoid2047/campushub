/// Auth domain contract (docs/06-api-design.md section 2,
/// docs/08-security-design.md section 5).
library;

class UserProfile {
  const UserProfile({
    required this.id,
    required this.email,
    required this.fullName,
    required this.roles,
  });

  final String id;
  final String email;
  final String fullName;
  final List<String> roles;

  factory UserProfile.fromJson(Map<String, dynamic> json) => UserProfile(
        id: json['id'] as String,
        email: json['email'] as String,
        fullName: json['full_name'] as String,
        roles: (json['roles'] as List<dynamic>).cast<String>(),
      );
}

abstract class AuthRepository {
  /// True when a usable session exists (live token, or a stored refresh
  /// token that can be redeemed on next connectivity).
  Future<bool> hasSession();

  Future<UserProfile> login({
    required String tenantSlug,
    required String email,
    required String password,
  });

  Future<UserProfile> currentUser();

  Future<void> logout();
}
