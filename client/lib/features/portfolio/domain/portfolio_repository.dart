/// Portfolio domain (FR-PORT-1, Epic E10): the caller's own completed
/// courses and graded work — a read-only aggregation, always self-scoped
/// (there is no roster view; that's the admin/attendance modules' job).
library;

class PortfolioAssignmentEntry {
  const PortfolioAssignmentEntry({
    required this.assignmentId,
    required this.title,
    required this.score,
    required this.maxScore,
    required this.gradedAt,
  });

  final String assignmentId;
  final String title;
  final double score;
  final double maxScore;
  final DateTime gradedAt;

  factory PortfolioAssignmentEntry.fromJson(Map<String, dynamic> json) =>
      PortfolioAssignmentEntry(
        assignmentId: json['assignment_id'] as String,
        title: json['title'] as String,
        score: (json['score'] as num).toDouble(),
        maxScore: (json['max_score'] as num).toDouble(),
        gradedAt: DateTime.parse(json['graded_at'] as String),
      );
}

class PortfolioCourseEntry {
  const PortfolioCourseEntry({
    required this.courseId,
    required this.courseName,
    required this.courseCode,
    required this.term,
    required this.departmentName,
    required this.averageScorePercent,
    required this.assignments,
  });

  final String courseId;
  final String courseName;
  final String courseCode;
  final String term;
  final String departmentName;

  /// Null until at least one assignment in the course has been graded.
  final double? averageScorePercent;
  final List<PortfolioAssignmentEntry> assignments;

  factory PortfolioCourseEntry.fromJson(Map<String, dynamic> json) =>
      PortfolioCourseEntry(
        courseId: json['course_id'] as String,
        courseName: json['course_name'] as String,
        courseCode: json['course_code'] as String,
        term: json['term'] as String,
        departmentName: json['department_name'] as String,
        averageScorePercent:
            (json['average_score_percent'] as num?)?.toDouble(),
        assignments: [
          for (final row in json['assignments'] as List<dynamic>)
            PortfolioAssignmentEntry.fromJson(row as Map<String, dynamic>)
        ],
      );
}

class Portfolio {
  const Portfolio({
    required this.userId,
    required this.fullName,
    required this.courses,
  });

  final String userId;
  final String fullName;
  final List<PortfolioCourseEntry> courses;

  factory Portfolio.fromJson(Map<String, dynamic> json) => Portfolio(
        userId: json['user_id'] as String,
        fullName: json['full_name'] as String,
        courses: [
          for (final row in json['courses'] as List<dynamic>)
            PortfolioCourseEntry.fromJson(row as Map<String, dynamic>)
        ],
      );
}

abstract class PortfolioRepository {
  /// Requires connectivity, not cached — same reasoning as attendance and
  /// admin reports (docs/09 does not list this among cached reads).
  Future<Portfolio> myPortfolio();
}
