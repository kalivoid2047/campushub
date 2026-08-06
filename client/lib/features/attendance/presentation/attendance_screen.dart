import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/providers.dart';
import '../domain/attendance_repository.dart';

/// Per-course attendance report (FR-ATT-2). Server-side RBAC restricts this
/// to lecturers/admins; a student opening it sees the 403 surfaced as an
/// error rather than a bespoke "not for you" screen — the backend is the
/// single source of truth for who can see this. A "My attendance" action
/// covers the student side of that — no RBAC gate, since it's always the
/// caller's own record.
class CourseAttendanceScreen extends ConsumerWidget {
  const CourseAttendanceScreen(
      {super.key, required this.courseId, this.courseName});

  final String courseId;
  final String? courseName;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final repository = ref.watch(attendanceRepositoryProvider);
    return Scaffold(
      appBar: AppBar(
        title: Text('${courseName ?? 'Course'} — Attendance'),
        actions: [
          IconButton(
            tooltip: 'My attendance',
            icon: const Icon(Icons.person_outline),
            onPressed: () => showDialog<void>(
              context: context,
              builder: (_) => _MyAttendanceDialog(courseId: courseId),
            ),
          ),
        ],
      ),
      body: FutureBuilder<CourseAttendanceReport>(
        future: repository.courseReport(courseId),
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Text('${snapshot.error}'),
              ),
            );
          }
          final report = snapshot.data!;
          if (report.totalSessions == 0) {
            return const Center(child: Text('No completed sessions yet.'));
          }
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text(
                '${report.totalSessions} session${report.totalSessions == 1 ? '' : 's'} completed',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 12),
              for (final row in report.rows)
                Card(
                  child: ListTile(
                    title: Text(row.fullName),
                    subtitle: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(row.email,
                            style: Theme.of(context).textTheme.bodySmall),
                        const SizedBox(height: 4),
                        LinearProgressIndicator(value: row.attendanceRate),
                      ],
                    ),
                    trailing: Text(
                      '${row.sessionsAttended}/${row.totalSessions}\n'
                      '${(row.attendanceRate * 100).toStringAsFixed(0)}%',
                      textAlign: TextAlign.right,
                    ),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}

class _MyAttendanceDialog extends ConsumerWidget {
  const _MyAttendanceDialog({required this.courseId});

  final String courseId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final repository = ref.watch(attendanceRepositoryProvider);
    return AlertDialog(
      title: const Text('My attendance'),
      content: FutureBuilder<MyAttendance>(
        future: repository.myAttendance(courseId),
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const SizedBox(
              height: 60,
              child: Center(child: CircularProgressIndicator()),
            );
          }
          if (snapshot.hasError) {
            return Text('${snapshot.error}');
          }
          final mine = snapshot.data!;
          if (mine.totalSessions == 0) {
            return const Text('No completed sessions yet.');
          }
          return Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '${(mine.attendanceRate * 100).toStringAsFixed(0)}% attended',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 8),
              LinearProgressIndicator(value: mine.attendanceRate),
              const SizedBox(height: 8),
              Text(
                  '${mine.sessionsAttended} of ${mine.totalSessions} sessions'),
            ],
          );
        },
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Close'),
        ),
      ],
    );
  }
}
