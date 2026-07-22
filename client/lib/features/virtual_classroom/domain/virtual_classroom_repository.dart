/// Virtual classroom domain — session lifecycle (docs/10-virtual-classroom.md)
/// plus the LiveKit media credentials minted per-join.
library;

class ClassSessionSummary {
  const ClassSessionSummary({
    required this.id,
    required this.courseId,
    required this.title,
    required this.status,
    this.scheduledStart,
    this.scheduledEnd,
    this.actualStart,
    this.actualEnd,
  });

  final String id;
  final String courseId;
  final String title;
  final String status; // scheduled | live | ended | cancelled
  final DateTime? scheduledStart;
  final DateTime? scheduledEnd;
  final DateTime? actualStart;
  final DateTime? actualEnd;

  factory ClassSessionSummary.fromJson(Map<String, dynamic> json) =>
      ClassSessionSummary(
        id: json['id'] as String,
        courseId: json['course_id'] as String,
        title: json['title'] as String,
        status: json['status'] as String,
        scheduledStart: _parse(json['scheduled_start']),
        scheduledEnd: _parse(json['scheduled_end']),
        actualStart: _parse(json['actual_start']),
        actualEnd: _parse(json['actual_end']),
      );

  static DateTime? _parse(dynamic value) =>
      value == null ? null : DateTime.parse(value as String);
}

/// Result of joining a live session: attendance is always recorded
/// server-side (FR-VC-5); [canOpenCall] is false when the backend's
/// LiveKit server isn't configured, in which case the caller should show
/// "recorded as present" without attempting to open a call.
class JoinInfo {
  const JoinInfo({
    required this.joinedAt,
    required this.signalingUrl,
    required this.sfuToken,
  });

  final DateTime joinedAt;
  final String? signalingUrl;
  final String? sfuToken;

  bool get canOpenCall => signalingUrl != null && sfuToken != null;

  factory JoinInfo.fromJson(Map<String, dynamic> json) => JoinInfo(
        joinedAt: DateTime.parse(json['joined_at'] as String),
        signalingUrl: json['signaling_url'] as String?,
        sfuToken: json['sfu_token'] as String?,
      );
}

abstract class VirtualClassroomRepository {
  /// Requires connectivity — sessions are not cached (docs/09 does not list
  /// this among the offline-cached reads; a live class inherently needs a
  /// connection anyway).
  Future<List<ClassSessionSummary>> listSessions(String courseId);

  Future<ClassSessionSummary> createSession(String courseId, String title);

  Future<ClassSessionSummary> start(String sessionId);

  Future<ClassSessionSummary> end(String sessionId);

  /// Records attendance and, when LiveKit is configured server-side,
  /// returns a room-join token for opening the live call.
  Future<JoinInfo> join(String sessionId);

  Future<void> leave(String sessionId);
}
