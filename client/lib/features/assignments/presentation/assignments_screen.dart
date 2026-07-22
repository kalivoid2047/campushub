import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/providers.dart';
import '../domain/assignments_repository.dart';

/// Assignments list for a course, with an inline submit sheet (Epic E4).
class AssignmentsScreen extends ConsumerStatefulWidget {
  const AssignmentsScreen({super.key, required this.courseId, this.courseName});

  final String courseId;
  final String? courseName;

  @override
  ConsumerState<AssignmentsScreen> createState() => _AssignmentsScreenState();
}

class _AssignmentsScreenState extends ConsumerState<AssignmentsScreen> {
  late Future<List<AssignmentSummary>> _future;

  @override
  void initState() {
    super.initState();
    _future = ref
        .read(assignmentsRepositoryProvider)
        .listAssignments(widget.courseId);
  }

  Future<void> _openSubmitSheet(AssignmentSummary assignment) async {
    final controller = TextEditingController();
    final submitted = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (sheetContext) => Padding(
        padding: EdgeInsets.only(
          left: 16,
          right: 16,
          top: 16,
          bottom: MediaQuery.of(sheetContext).viewInsets.bottom + 16,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              assignment.title,
              style: Theme.of(sheetContext).textTheme.titleLarge,
            ),
            if (assignment.dueAt != null)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text('Due ${assignment.dueAt!.toLocal()}'),
              ),
            const SizedBox(height: 12),
            TextField(
              controller: controller,
              maxLines: 6,
              decoration: const InputDecoration(
                labelText: 'Your answer',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            FilledButton.icon(
              icon: const Icon(Icons.send),
              label: const Text('Submit'),
              onPressed: () => Navigator.of(sheetContext).pop(true),
            ),
          ],
        ),
      ),
    );
    if (submitted != true || !mounted) return;

    final outcome = await ref.read(assignmentsRepositoryProvider).submit(
      assignmentId: assignment.id,
      content: {'text': controller.text},
    );
    if (!mounted) return;
    final message = switch (outcome.delivery) {
      SubmissionDelivery.submitted when outcome.status == 'late' =>
        'Submitted (marked late)',
      SubmissionDelivery.submitted => 'Submitted',
      SubmissionDelivery.queuedOffline =>
        'Saved — will submit when back online',
    };
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar:
          AppBar(title: Text('${widget.courseName ?? 'Course'} — Assignments')),
      body: FutureBuilder<List<AssignmentSummary>>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return Center(child: Text('${snapshot.error}'));
          }
          final assignments = snapshot.data ?? const [];
          if (assignments.isEmpty) {
            return const Center(child: Text('No assignments yet.'));
          }
          return ListView.builder(
            itemCount: assignments.length,
            itemBuilder: (context, index) {
              final assignment = assignments[index];
              final overdue = assignment.dueAt != null &&
                  assignment.dueAt!.isBefore(DateTime.now());
              return ListTile(
                leading: const Icon(Icons.assignment_outlined),
                title: Text(assignment.title),
                subtitle: Text(
                  assignment.dueAt == null
                      ? 'No due date'
                      : '${overdue ? 'Was due' : 'Due'} ${assignment.dueAt!.toLocal()}',
                ),
                trailing: overdue
                    ? Chip(
                        label: const Text('overdue'),
                        visualDensity: VisualDensity.compact,
                        backgroundColor:
                            Theme.of(context).colorScheme.errorContainer,
                      )
                    : null,
                onTap: () => _openSubmitSheet(assignment),
              );
            },
          );
        },
      ),
    );
  }
}
