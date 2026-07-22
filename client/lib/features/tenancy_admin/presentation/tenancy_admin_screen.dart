import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/providers.dart';
import '../../../core/error/app_exception.dart';
import '../../shared/status_chip.dart';
import '../domain/tenancy_admin_repository.dart';

/// Tenant administration console (Epic E8): storage/engagement overview,
/// department & course structure, user creation & enrollment, and the
/// read-only audit trail. Every action here maps to an already-functional
/// backend endpoint (backend/app/modules/admin, backend/app/modules/iam)
/// that previously had no client surface. RBAC is enforced server-side —
/// this screen surfaces a 403 as a plain error rather than guessing locally
/// who is allowed to see what (docs/08 section 7).
class TenancyAdminScreen extends StatelessWidget {
  const TenancyAdminScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 4,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Tenant Administration'),
          bottom: const TabBar(tabs: [
            Tab(icon: Icon(Icons.dashboard_outlined), text: 'Overview'),
            Tab(icon: Icon(Icons.account_tree_outlined), text: 'Structure'),
            Tab(icon: Icon(Icons.people_outline), text: 'People'),
            Tab(icon: Icon(Icons.receipt_long_outlined), text: 'Audit log'),
          ]),
        ),
        body: const TabBarView(children: [
          _OverviewTab(),
          _StructureTab(),
          _PeopleTab(),
          _AuditLogTab(),
        ]),
      ),
    );
  }
}

class _ErrorRetry extends StatelessWidget {
  const _ErrorRetry({required this.message, this.onRetry});

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(message, textAlign: TextAlign.center),
            if (onRetry != null) ...[
              const SizedBox(height: 12),
              OutlinedButton(onPressed: onRetry, child: const Text('Retry')),
            ],
          ],
        ),
      ),
    );
  }
}

String _formatBytes(int bytes) {
  if (bytes >= 1024 * 1024 * 1024) {
    return '${(bytes / (1024 * 1024 * 1024)).toStringAsFixed(1)} GB';
  }
  if (bytes >= 1024 * 1024) {
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }
  if (bytes >= 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
  return '$bytes B';
}

/// Storage quota gauge + basic engagement counts (FR-ADM-3).
class _OverviewTab extends ConsumerStatefulWidget {
  const _OverviewTab();

  @override
  ConsumerState<_OverviewTab> createState() => _OverviewTabState();
}

class _OverviewTabState extends ConsumerState<_OverviewTab> {
  late Future<(StorageUsage, EngagementCounts)> _future;

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _load() {
    _future = _fetch();
  }

  Future<(StorageUsage, EngagementCounts)> _fetch() async {
    final repo = ref.read(tenancyAdminRepositoryProvider);
    final storage = await repo.storageUsage();
    final engagement = await repo.engagement();
    return (storage, engagement);
  }

  Future<void> _refresh() async {
    setState(_load);
    await _future;
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<(StorageUsage, EngagementCounts)>(
      future: _future,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return _ErrorRetry(message: '${snapshot.error}', onRetry: _refresh);
        }
        final (storage, engagement) = snapshot.data!;
        return RefreshIndicator(
          onRefresh: _refresh,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Storage', style: Theme.of(context).textTheme.titleMedium),
                      const SizedBox(height: 12),
                      ClipRRect(
                        borderRadius: BorderRadius.circular(4),
                        child: LinearProgressIndicator(
                          value: (storage.percentUsed / 100).clamp(0, 1),
                          minHeight: 8,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        '${_formatBytes(storage.usedBytes)} of '
                        '${_formatBytes(storage.quotaBytes)} used '
                        '(${storage.percentUsed.toStringAsFixed(1)}%)',
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
              Text('Engagement', style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 8),
              GridView.count(
                crossAxisCount: 2,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                mainAxisSpacing: 8,
                crossAxisSpacing: 8,
                childAspectRatio: 2.2,
                children: [
                  _StatCard(label: 'Users', value: engagement.users, icon: Icons.people_outline),
                  _StatCard(
                      label: 'Resources', value: engagement.resources, icon: Icons.folder_outlined),
                  _StatCard(
                      label: 'Messages', value: engagement.messages, icon: Icons.chat_bubble_outline),
                  _StatCard(
                      label: 'Submissions',
                      value: engagement.submissions,
                      icon: Icons.assignment_turned_in_outlined),
                ],
              ),
            ],
          ),
        );
      },
    );
  }
}

class _StatCard extends StatelessWidget {
  const _StatCard({required this.label, required this.value, required this.icon});

  final String label;
  final int value;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: Row(
          children: [
            Icon(icon, color: Theme.of(context).colorScheme.primary),
            const SizedBox(width: 12),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text('$value', style: Theme.of(context).textTheme.titleLarge),
                Text(label, style: Theme.of(context).textTheme.bodySmall),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// Departments and courses (FR-ADM-1). dept_admin can create courses only;
/// department creation requires institution_admin/super_admin — enforced
/// server-side, surfaced here as a plain error on submit.
class _StructureTab extends ConsumerStatefulWidget {
  const _StructureTab();

  @override
  ConsumerState<_StructureTab> createState() => _StructureTabState();
}

class _StructureTabState extends ConsumerState<_StructureTab> {
  late Future<List<AdminDepartment>> _departmentsFuture;
  late Future<List<AdminCourse>> _coursesFuture;
  List<AdminDepartment> _departments = const [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _load() {
    final repo = ref.read(tenancyAdminRepositoryProvider);
    _departmentsFuture = repo.listDepartments()
      ..then((value) {
        if (mounted) setState(() => _departments = value);
      });
    _coursesFuture = repo.listCourses();
  }

  Future<void> _refresh() async {
    setState(_load);
    await Future.wait([_departmentsFuture, _coursesFuture]);
  }

  Future<void> _addDepartment() async {
    final nameController = TextEditingController();
    final codeController = TextEditingController();
    final created = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('New department'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: nameController,
              decoration: const InputDecoration(labelText: 'Name'),
              autofocus: true,
            ),
            const SizedBox(height: 8),
            TextField(
              controller: codeController,
              decoration: const InputDecoration(labelText: 'Code', helperText: 'e.g. CS'),
              textCapitalization: TextCapitalization.characters,
            ),
          ],
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(false),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: () => Navigator.of(dialogContext).pop(true), child: const Text('Create')),
        ],
      ),
    );
    if (created != true || !mounted) return;
    if (nameController.text.trim().isEmpty || codeController.text.trim().isEmpty) return;
    try {
      await ref.read(tenancyAdminRepositoryProvider).createDepartment(
            name: nameController.text.trim(),
            code: codeController.text.trim(),
          );
      if (mounted) setState(_load);
    } on AppException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(error.message)));
      }
    }
  }

  Future<void> _addCourse() async {
    if (_departments.isEmpty) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Create a department first.')));
      return;
    }
    final nameController = TextEditingController();
    final codeController = TextEditingController();
    final termController = TextEditingController();
    var departmentId = _departments.first.id;
    final created = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (dialogContext, setDialogState) => AlertDialog(
          title: const Text('New course'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              DropdownButtonFormField<String>(
                initialValue: departmentId,
                decoration: const InputDecoration(labelText: 'Department'),
                items: [
                  for (final department in _departments)
                    DropdownMenuItem(value: department.id, child: Text(department.name)),
                ],
                onChanged: (value) => setDialogState(() => departmentId = value!),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: nameController,
                decoration: const InputDecoration(labelText: 'Name'),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: codeController,
                decoration:
                    const InputDecoration(labelText: 'Code', helperText: 'e.g. CS101'),
                textCapitalization: TextCapitalization.characters,
              ),
              const SizedBox(height: 8),
              TextField(
                controller: termController,
                decoration:
                    const InputDecoration(labelText: 'Term', helperText: 'e.g. 2026-fall'),
              ),
            ],
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.of(dialogContext).pop(false),
                child: const Text('Cancel')),
            FilledButton(
                onPressed: () => Navigator.of(dialogContext).pop(true),
                child: const Text('Create')),
          ],
        ),
      ),
    );
    if (created != true || !mounted) return;
    if ([nameController.text, codeController.text, termController.text]
        .any((value) => value.trim().isEmpty)) {
      return;
    }
    try {
      await ref.read(tenancyAdminRepositoryProvider).createCourse(
            departmentId: departmentId,
            name: nameController.text.trim(),
            code: codeController.text.trim(),
            term: termController.text.trim(),
          );
      if (mounted) setState(_load);
    } on AppException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(error.message)));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: _refresh,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Row(
            children: [
              Expanded(
                  child: Text('Departments', style: Theme.of(context).textTheme.titleMedium)),
              IconButton(
                tooltip: 'Add department',
                icon: const Icon(Icons.add_circle_outline),
                onPressed: _addDepartment,
              ),
            ],
          ),
          FutureBuilder<List<AdminDepartment>>(
            future: _departmentsFuture,
            builder: (context, snapshot) {
              if (snapshot.connectionState != ConnectionState.done) {
                return const Padding(
                  padding: EdgeInsets.symmetric(vertical: 16),
                  child: Center(child: CircularProgressIndicator()),
                );
              }
              if (snapshot.hasError) return _ErrorRetry(message: '${snapshot.error}');
              final departments = snapshot.data ?? const [];
              if (departments.isEmpty) {
                return const Padding(
                  padding: EdgeInsets.symmetric(vertical: 8),
                  child: Text('No departments yet.'),
                );
              }
              return Column(
                children: [
                  for (final department in departments)
                    ListTile(
                      leading: const Icon(Icons.account_tree_outlined),
                      title: Text(department.name),
                      subtitle: Text(department.code),
                    ),
                ],
              );
            },
          ),
          const Divider(height: 32),
          Row(
            children: [
              Expanded(child: Text('Courses', style: Theme.of(context).textTheme.titleMedium)),
              IconButton(
                tooltip: 'Add course',
                icon: const Icon(Icons.add_circle_outline),
                onPressed: _addCourse,
              ),
            ],
          ),
          FutureBuilder<List<AdminCourse>>(
            future: _coursesFuture,
            builder: (context, snapshot) {
              if (snapshot.connectionState != ConnectionState.done) {
                return const Padding(
                  padding: EdgeInsets.symmetric(vertical: 16),
                  child: Center(child: CircularProgressIndicator()),
                );
              }
              if (snapshot.hasError) return _ErrorRetry(message: '${snapshot.error}');
              final courses = snapshot.data ?? const [];
              if (courses.isEmpty) {
                return const Padding(
                  padding: EdgeInsets.symmetric(vertical: 8),
                  child: Text('No courses yet.'),
                );
              }
              return Column(
                children: [
                  for (final course in courses)
                    ListTile(
                      leading: const Icon(Icons.school_outlined),
                      title: Text(course.name),
                      subtitle: Text('${course.code} • ${course.term}'),
                    ),
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}

/// User creation + course enrollment (FR-ADM-1). The enrollment picker reads
/// from GET /api/v1/admin/users, the tenant's user directory.
class _PeopleTab extends ConsumerStatefulWidget {
  const _PeopleTab();

  @override
  ConsumerState<_PeopleTab> createState() => _PeopleTabState();
}

class _PeopleTabState extends ConsumerState<_PeopleTab> {
  final _createFormKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _fullNameController = TextEditingController();
  String _newUserRole = userRoles.first;
  bool _creatingUser = false;
  TenantUser? _lastCreatedUser;

  final _enrollFormKey = GlobalKey<FormState>();
  String _enrollmentRole = courseEnrollmentRoles.first;
  String? _enrollCourseId;
  String? _enrollUserId;
  bool _enrolling = false;
  late Future<List<AdminCourse>> _coursesFuture;
  late Future<List<TenantUser>> _usersFuture;

  @override
  void initState() {
    super.initState();
    _coursesFuture = ref.read(tenancyAdminRepositoryProvider).listCourses();
    _usersFuture = ref.read(tenancyAdminRepositoryProvider).listUsers();
  }

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    _fullNameController.dispose();
    super.dispose();
  }

  Future<void> _createUser() async {
    if (!(_createFormKey.currentState?.validate() ?? false)) return;
    setState(() => _creatingUser = true);
    try {
      final user = await ref.read(tenancyAdminRepositoryProvider).createUser(
            email: _emailController.text.trim(),
            password: _passwordController.text,
            fullName: _fullNameController.text.trim(),
            role: _newUserRole,
          );
      if (!mounted) return;
      setState(() {
        _lastCreatedUser = user;
        // Refresh so the new user is immediately pickable below.
        _usersFuture = ref.read(tenancyAdminRepositoryProvider).listUsers();
        _enrollUserId = user.id;
      });
      _emailController.clear();
      _passwordController.clear();
      _fullNameController.clear();
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Created ${user.fullName}')));
    } on AppException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(error.message)));
      }
    } finally {
      if (mounted) setState(() => _creatingUser = false);
    }
  }

  Future<void> _enroll() async {
    if (_enrollCourseId == null) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Choose a course.')));
      return;
    }
    if (_enrollUserId == null) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Choose a user.')));
      return;
    }
    setState(() => _enrolling = true);
    try {
      await ref.read(tenancyAdminRepositoryProvider).enrollUser(
            courseId: _enrollCourseId!,
            userId: _enrollUserId!,
            role: _enrollmentRole,
          );
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('Enrolled.')));
    } on AppException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(error.message)));
      }
    } finally {
      if (mounted) setState(() => _enrolling = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Form(
              key: _createFormKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Create user', style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 12),
                  TextFormField(
                    controller: _fullNameController,
                    decoration: const InputDecoration(labelText: 'Full name'),
                    validator: (value) =>
                        (value == null || value.trim().isEmpty) ? 'Required' : null,
                  ),
                  const SizedBox(height: 8),
                  TextFormField(
                    controller: _emailController,
                    decoration: const InputDecoration(labelText: 'Email'),
                    keyboardType: TextInputType.emailAddress,
                    validator: (value) =>
                        (value == null || !value.contains('@')) ? 'Enter a valid email' : null,
                  ),
                  const SizedBox(height: 8),
                  TextFormField(
                    controller: _passwordController,
                    decoration: const InputDecoration(labelText: 'Temporary password'),
                    obscureText: true,
                    validator: (value) =>
                        (value == null || value.length < 8) ? 'At least 8 characters' : null,
                  ),
                  const SizedBox(height: 8),
                  DropdownButtonFormField<String>(
                    initialValue: _newUserRole,
                    decoration: const InputDecoration(labelText: 'Role'),
                    items: [
                      for (final role in userRoles) DropdownMenuItem(value: role, child: Text(role)),
                    ],
                    onChanged: (value) => setState(() => _newUserRole = value!),
                  ),
                  const SizedBox(height: 12),
                  if (_lastCreatedUser != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 12),
                      child: Wrap(
                        crossAxisAlignment: WrapCrossAlignment.center,
                        spacing: 8,
                        children: [
                          const Text('Last created:'),
                          StatusChip(
                            label: _lastCreatedUser!.id,
                            color: Theme.of(context).colorScheme.primary,
                            icon: Icons.badge_outlined,
                          ),
                        ],
                      ),
                    ),
                  Align(
                    alignment: Alignment.centerRight,
                    child: FilledButton.icon(
                      onPressed: _creatingUser ? null : _createUser,
                      icon: _creatingUser
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(strokeWidth: 2))
                          : const Icon(Icons.person_add_alt),
                      label: const Text('Create'),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
        const SizedBox(height: 16),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Form(
              key: _enrollFormKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Enroll in a course', style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 12),
                  FutureBuilder<List<AdminCourse>>(
                    future: _coursesFuture,
                    builder: (context, snapshot) {
                      final courses = snapshot.data ?? const [];
                      _enrollCourseId ??= courses.isNotEmpty ? courses.first.id : null;
                      return DropdownButtonFormField<String>(
                        initialValue: _enrollCourseId,
                        decoration: const InputDecoration(labelText: 'Course'),
                        items: [
                          for (final course in courses)
                            DropdownMenuItem(
                                value: course.id, child: Text('${course.code} — ${course.name}')),
                        ],
                        onChanged: (value) => setState(() => _enrollCourseId = value),
                      );
                    },
                  ),
                  const SizedBox(height: 8),
                  FutureBuilder<List<TenantUser>>(
                    future: _usersFuture,
                    builder: (context, snapshot) {
                      if (snapshot.connectionState != ConnectionState.done) {
                        return const Padding(
                          padding: EdgeInsets.symmetric(vertical: 8),
                          child: LinearProgressIndicator(),
                        );
                      }
                      if (snapshot.hasError) {
                        return _ErrorRetry(
                          message: '${snapshot.error}',
                          onRetry: () => setState(() {
                            _usersFuture =
                                ref.read(tenancyAdminRepositoryProvider).listUsers();
                          }),
                        );
                      }
                      final users = snapshot.data ?? const [];
                      if (users.isEmpty) {
                        return const Padding(
                          padding: EdgeInsets.symmetric(vertical: 8),
                          child: Text('No users yet — create one above.'),
                        );
                      }
                      _enrollUserId ??= users.first.id;
                      return DropdownButtonFormField<String>(
                        initialValue: _enrollUserId,
                        decoration: const InputDecoration(labelText: 'User'),
                        items: [
                          for (final user in users)
                            DropdownMenuItem(
                              value: user.id,
                              child: Text('${user.fullName} — ${user.email}'),
                            ),
                        ],
                        onChanged: (value) => setState(() => _enrollUserId = value),
                      );
                    },
                  ),
                  const SizedBox(height: 8),
                  DropdownButtonFormField<String>(
                    initialValue: _enrollmentRole,
                    decoration: const InputDecoration(labelText: 'Enrollment role'),
                    items: [
                      for (final role in courseEnrollmentRoles)
                        DropdownMenuItem(value: role, child: Text(role)),
                    ],
                    onChanged: (value) => setState(() => _enrollmentRole = value!),
                  ),
                  const SizedBox(height: 12),
                  Align(
                    alignment: Alignment.centerRight,
                    child: FilledButton.icon(
                      onPressed: _enrolling ? null : _enroll,
                      icon: _enrolling
                          ? const SizedBox(
                              width: 16,
                              height: 16,
                              child: CircularProgressIndicator(strokeWidth: 2))
                          : const Icon(Icons.how_to_reg_outlined),
                      label: const Text('Enroll'),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}

/// Read-only, append-only audit trail (docs/08 section 9), newest first,
/// paginated with a manual "load more" rather than infinite scroll — audit
/// review is a deliberate act, not a feed to skim.
class _AuditLogTab extends ConsumerStatefulWidget {
  const _AuditLogTab();

  @override
  ConsumerState<_AuditLogTab> createState() => _AuditLogTabState();
}

class _AuditLogTabState extends ConsumerState<_AuditLogTab> {
  static const _pageSize = 50;

  final List<AdminAuditLogEntry> _entries = [];
  bool _loading = false;
  bool _hasMore = true;
  Object? _error;

  @override
  void initState() {
    super.initState();
    _loadMore();
  }

  Future<void> _loadMore() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final page = await ref.read(tenancyAdminRepositoryProvider).auditLogs(
            limit: _pageSize,
            offset: _entries.length,
          );
      if (!mounted) return;
      setState(() {
        _entries.addAll(page);
        _hasMore = page.length == _pageSize;
      });
    } catch (error) {
      if (mounted) setState(() => _error = error);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _refresh() async {
    setState(() {
      _entries.clear();
      _hasMore = true;
    });
    await _loadMore();
  }

  @override
  Widget build(BuildContext context) {
    if (_entries.isEmpty && _loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_entries.isEmpty && _error != null) {
      return _ErrorRetry(message: '$_error', onRetry: _refresh);
    }
    if (_entries.isEmpty) {
      return const Center(child: Text('No audit entries yet.'));
    }
    return RefreshIndicator(
      onRefresh: _refresh,
      child: ListView.builder(
        padding: const EdgeInsets.symmetric(vertical: 8),
        itemCount: _entries.length + 1,
        itemBuilder: (context, index) {
          if (index == _entries.length) {
            return Padding(
              padding: const EdgeInsets.all(16),
              child: Center(
                child: !_hasMore
                    ? const Text('End of log.')
                    : _loading
                        ? const CircularProgressIndicator()
                        : OutlinedButton(
                            onPressed: _loadMore, child: const Text('Load more')),
              ),
            );
          }
          final entry = _entries[index];
          final target = entry.targetType == null
              ? null
              : '${entry.targetType}${entry.targetId != null ? ' ${entry.targetId}' : ''}';
          return ListTile(
            leading: const Icon(Icons.history),
            title: Text(entry.action),
            subtitle: Text([
              if (target != null) target,
              if (entry.actorId != null) 'by ${entry.actorId}',
            ].join(' • ')),
            trailing: Text(
              '${entry.createdAt.toLocal()}'.split('.').first,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          );
        },
      ),
    );
  }
}
