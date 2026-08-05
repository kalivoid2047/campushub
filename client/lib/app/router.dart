import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/sync/sync_engine.dart';
import '../features/assignments/presentation/assignments_screen.dart';
import '../features/attendance/presentation/attendance_screen.dart';
import '../features/auth/presentation/auth_screen.dart';
import '../features/communication/presentation/communication_screen.dart';
import '../features/portfolio/presentation/portfolio_screen.dart';
import '../features/resources/presentation/resources_screen.dart';
import '../features/search/presentation/search_screen.dart';
import '../features/tenancy_admin/presentation/tenancy_admin_screen.dart';
import '../features/virtual_classroom/presentation/virtual_classroom_screen.dart';
import 'providers.dart';

/// Roles that see the admin console entry point (docs/08 section 7 RBAC
/// matrix — mirrors the backend's _STRUCTURE_ADMIN / _COURSE_ADMIN guards
/// across the admin module's endpoints).
const _adminRoles = {'dept_admin', 'institution_admin', 'super_admin'};

/// App routes (docs/07-ui-ux.md section 1).
final GoRouter appRouter = GoRouter(
  initialLocation: '/login',
  routes: [
    GoRoute(path: '/login', builder: (context, state) => const AuthScreen()),
    GoRoute(path: '/home', builder: (context, state) => const HomeShell()),
    GoRoute(path: '/search', builder: (context, state) => const SearchScreen()),
    GoRoute(
      path: '/courses/:courseId',
      builder: (context, state) => CourseDetailScreen(
        courseId: state.pathParameters['courseId']!,
        courseName: state.extra as String?,
      ),
    ),
    GoRoute(
      path: '/courses/:courseId/assignments',
      builder: (context, state) => AssignmentsScreen(
        courseId: state.pathParameters['courseId']!,
        courseName: state.extra as String?,
      ),
    ),
    GoRoute(
      path: '/modules/:moduleId',
      builder: (context, state) => ModuleResourcesScreen(
        moduleId: state.pathParameters['moduleId']!,
        moduleTitle: state.extra as String?,
      ),
    ),
    GoRoute(
      path: '/channels/:channelId',
      builder: (context, state) => MessageThreadScreen(
        channelId: state.pathParameters['channelId']!,
        title: state.extra as String?,
      ),
    ),
    GoRoute(
      path: '/courses/:courseId/sessions',
      builder: (context, state) => SessionsScreen(
        courseId: state.pathParameters['courseId']!,
        courseName: state.extra as String?,
      ),
    ),
    GoRoute(
      path: '/courses/:courseId/attendance',
      builder: (context, state) => CourseAttendanceScreen(
        courseId: state.pathParameters['courseId']!,
        courseName: state.extra as String?,
      ),
    ),
    GoRoute(
      path: '/admin',
      builder: (context, state) => const TenancyAdminScreen(),
    ),
    GoRoute(
      path: '/portfolio',
      builder: (context, state) => const PortfolioScreen(),
    ),
  ],
);

/// Signed-in shell: bottom navigation (mobile-first per docs/07 section 2)
/// with Courses and Announcements, background sync (docs/09 section 4),
/// a manual sync action, and the sync-status chip (FR-SYNC-4).
class HomeShell extends ConsumerStatefulWidget {
  const HomeShell({super.key});

  @override
  ConsumerState<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends ConsumerState<HomeShell> {
  int _tab = 0;
  bool _syncing = false;
  bool _isAdmin = false;
  StreamSubscription<SyncResult>? _resultsSub;

  @override
  void initState() {
    super.initState();
    final scheduler = ref.read(syncSchedulerProvider);
    _resultsSub = scheduler.results.listen((result) {
      if (!mounted) return;
      ref.read(lastSyncResultProvider.notifier).state = result;
      setState(() => _syncing = false);
    });
    scheduler.start();

    // Determines whether the admin-console entry shows; the backend is the
    // actual authority (docs/08 section 7) — this only avoids putting a
    // dead-end control in front of students/lecturers.
    ref.read(authRepositoryProvider).currentUser().then((profile) {
      if (mounted) {
        setState(() => _isAdmin = profile.roles.any(_adminRoles.contains));
      }
    });
  }

  @override
  void dispose() {
    _resultsSub?.cancel();
    super.dispose();
  }

  Future<void> _runSync() async {
    setState(() => _syncing = true);
    await ref.read(syncSchedulerProvider).runNow();
  }

  @override
  Widget build(BuildContext context) {
    final lastSync = ref.watch(lastSyncResultProvider);
    final (chipLabel, chipIcon) = switch (lastSync) {
      null => ('Not synced', Icons.cloud_queue),
      final r when r.offline => ('Offline', Icons.cloud_off_outlined),
      final r when r.conflicts > 0 => (
          '${r.conflicts} conflicts',
          Icons.sync_problem
        ),
      _ => ('Synced', Icons.cloud_done_outlined),
    };

    return Scaffold(
      appBar: AppBar(
        title: const Text('CampusHub'),
        actions: [
          if (_isAdmin)
            IconButton(
              tooltip: 'Tenant administration',
              icon: const Icon(Icons.admin_panel_settings_outlined),
              onPressed: () => context.push('/admin'),
            ),
          IconButton(
            tooltip: 'My portfolio',
            icon: const Icon(Icons.badge_outlined),
            onPressed: () => context.push('/portfolio'),
          ),
          IconButton(
            tooltip: 'Search',
            icon: const Icon(Icons.search),
            onPressed: () => context.push('/search'),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 10),
            child: Chip(
              avatar: Icon(chipIcon, size: 16),
              label: Text(chipLabel),
              visualDensity: VisualDensity.compact,
            ),
          ),
          IconButton(
            tooltip: 'Sync now',
            onPressed: _syncing ? null : _runSync,
            icon: _syncing
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.sync),
          ),
          IconButton(
            tooltip: 'Sign out',
            icon: const Icon(Icons.logout),
            onPressed: () async {
              await ref.read(authRepositoryProvider).logout();
              if (context.mounted) context.go('/login');
            },
          ),
        ],
      ),
      body: switch (_tab) {
        0 => const CoursesTab(),
        _ => const AnnouncementsTab(),
      },
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (index) => setState(() => _tab = index),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.school_outlined),
            selectedIcon: Icon(Icons.school),
            label: 'Courses',
          ),
          NavigationDestination(
            icon: Icon(Icons.campaign_outlined),
            selectedIcon: Icon(Icons.campaign),
            label: 'Announcements',
          ),
        ],
      ),
    );
  }
}
