/// Assignments domain (client side of Epic E4, FR-ASG-2 offline submission).
library;

class AssignmentSummary {
  const AssignmentSummary({
    required this.id,
    required this.courseId,
    required this.title,
    required this.instructions,
    required this.maxScore,
    this.dueAt,
  });

  final String id;
  final String courseId;
  final String title;
  final String instructions;
  final double maxScore;
  final DateTime? dueAt;

  factory AssignmentSummary.fromJson(Map<String, dynamic> json) =>
      AssignmentSummary(
        id: json['id'] as String,
        courseId: json['course_id'] as String,
        title: json['title'] as String,
        instructions: json['instructions'] as String? ?? '',
        maxScore: (json['max_score'] as num?)?.toDouble() ?? 100,
        dueAt: json['due_at'] == null
            ? null
            : DateTime.parse(json['due_at'] as String),
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'course_id': courseId,
        'title': title,
        'instructions': instructions,
        'max_score': maxScore,
        'due_at': dueAt?.toIso8601String(),
      };
}

/// Outcome of a submit attempt: delivered now, or queued for sync.
enum SubmissionDelivery { submitted, queuedOffline }

class SubmitOutcome {
  const SubmitOutcome(this.delivery, {this.status});

  final SubmissionDelivery delivery;

  /// Server-reported submission status when delivered online
  /// (submitted/late); null when queued offline.
  final String? status;
}

abstract class AssignmentsRepository {
  /// Network-first with cache fallback (docs/09 section 7).
  Future<List<AssignmentSummary>> listAssignments(String courseId);

  /// Submit (finalize=true) or save a draft. Online: straight to the REST
  /// endpoint. Offline: enqueued to sync_queue and delivered by the next
  /// sync cycle — never lost, never blocked on connectivity (FR-ASG-2).
  Future<SubmitOutcome> submit({
    required String assignmentId,
    required Map<String, dynamic> content,
    bool finalize = true,
  });
}
