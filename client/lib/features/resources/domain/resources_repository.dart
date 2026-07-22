/// Catalog domain: courses → modules → resources (Epic E2 client side,
/// docs/09-offline-sync.md network-first read pattern).
library;

class CourseSummary {
  const CourseSummary({
    required this.id,
    required this.name,
    required this.code,
    required this.term,
  });

  final String id;
  final String name;
  final String code;
  final String term;

  factory CourseSummary.fromJson(Map<String, dynamic> json) => CourseSummary(
        id: json['id'] as String,
        name: json['name'] as String,
        code: json['code'] as String,
        term: json['term'] as String,
      );

  Map<String, dynamic> toJson() =>
      {'id': id, 'name': name, 'code': code, 'term': term};
}

class ModuleSummary {
  const ModuleSummary({
    required this.id,
    required this.courseId,
    required this.title,
    required this.position,
  });

  final String id;
  final String courseId;
  final String title;
  final int position;

  factory ModuleSummary.fromJson(Map<String, dynamic> json) => ModuleSummary(
        id: json['id'] as String,
        courseId: json['course_id'] as String,
        title: json['title'] as String,
        position: json['position'] as int? ?? 0,
      );

  Map<String, dynamic> toJson() =>
      {'id': id, 'course_id': courseId, 'title': title, 'position': position};
}

class ResourceSummary {
  const ResourceSummary({
    required this.id,
    required this.moduleId,
    required this.title,
    required this.type,
    required this.versionNumber,
    required this.sizeBytes,
  });

  final String id;
  final String moduleId;
  final String title;
  final String type;
  final int versionNumber;
  final int sizeBytes;

  factory ResourceSummary.fromJson(Map<String, dynamic> json) {
    final version = json['current_version'] as Map<String, dynamic>?;
    return ResourceSummary(
      id: json['id'] as String,
      moduleId: json['module_id'] as String,
      title: json['title'] as String,
      type: json['type'] as String,
      versionNumber: version?['version_number'] as int? ??
          json['version_number'] as int? ??
          0,
      sizeBytes:
          version?['size_bytes'] as int? ?? json['size_bytes'] as int? ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'module_id': moduleId,
        'title': title,
        'type': type,
        'version_number': versionNumber,
        'size_bytes': sizeBytes,
      };
}

/// Reads are network-first with entity-cache fallback: fresh data when
/// online, cached data when the network is unavailable (docs/09 section 7).
abstract class CatalogRepository {
  Future<List<CourseSummary>> listCourses();
  Future<List<ModuleSummary>> listModules(String courseId);
  Future<List<ResourceSummary>> listResources(String moduleId);
}
