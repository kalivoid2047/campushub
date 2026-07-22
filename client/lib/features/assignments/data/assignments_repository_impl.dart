import 'dart:convert';

import '../../../core/error/app_exception.dart';
import '../../../core/network/api_client.dart';
import '../../../core/storage/local_database.dart';
import '../../../core/utils/uuid.dart';
import '../domain/assignments_repository.dart';

/// Assignments repository: network-first reads, offline-queued writes.
///
/// The offline submit path enqueues exactly the payload shape the backend's
/// SubmissionSyncHandler expects (backend
/// app/modules/assignments/sync_handler.py):
///   {"assignment_id": ..., "content": {...}, "finalize": true|false}
class AssignmentsRepositoryImpl implements AssignmentsRepository {
  AssignmentsRepositoryImpl(this._api, this._db);

  final ApiClient _api;
  final LocalDatabase _db;

  @override
  Future<List<AssignmentSummary>> listAssignments(String courseId) async {
    try {
      final rows =
          await _api.getJsonList('/api/v1/courses/$courseId/assignments');
      final assignments = [
        for (final row in rows)
          AssignmentSummary.fromJson(row as Map<String, dynamic>)
      ];
      for (final assignment in assignments) {
        await _db.upsertEntity(
          entityTable: 'assignments',
          entityId: assignment.id,
          payloadJson: jsonEncode(assignment.toJson()),
          serverVersion: 1,
        );
      }
      return assignments;
    } on NetworkUnavailableException {
      final cached = await _db.listEntities('assignments');
      return [
        for (final row in cached)
          AssignmentSummary.fromJson(
            jsonDecode(row['payload'] as String) as Map<String, dynamic>,
          )
      ].where((a) => a.courseId == courseId).toList();
    }
  }

  @override
  Future<SubmitOutcome> submit({
    required String assignmentId,
    required Map<String, dynamic> content,
    bool finalize = true,
  }) async {
    // client_id doubles as the sync idempotency key if this ends up queued.
    final clientId = newUuid();
    try {
      final response = await _api.postJson(
        '/api/v1/assignments/$assignmentId/submissions',
        {'content': content, 'client_id': clientId, 'finalize': finalize},
      );
      return SubmitOutcome(
        SubmissionDelivery.submitted,
        status: response['status'] as String?,
      );
    } on NetworkUnavailableException {
      await _db.enqueue(
        clientId: clientId,
        entityTable: 'submissions',
        entityId: newUuid(),
        operation: 'create',
        payloadJson: jsonEncode({
          'assignment_id': assignmentId,
          'content': content,
          'finalize': finalize,
        }),
      );
      return const SubmitOutcome(SubmissionDelivery.queuedOffline);
    }
  }
}
