import 'dart:convert';

import '../../../core/error/app_exception.dart';
import '../../../core/network/api_client.dart';
import '../../../core/storage/local_database.dart';
import '../domain/resources_repository.dart';

/// Network-first catalog reads with entity-cache fallback
/// (docs/09-offline-sync.md sections 1, 7).
///
/// Online: fetch, refresh the cache, return fresh data. Offline
/// (NetworkUnavailableException): serve whatever the cache holds — which the
/// SyncEngine's delta pull keeps reasonably current between explicit visits.
class CatalogRepositoryImpl implements CatalogRepository {
  CatalogRepositoryImpl(this._api, this._db);

  final ApiClient _api;
  final LocalDatabase _db;

  @override
  Future<List<CourseSummary>> listCourses() async {
    try {
      final rows = await _api.getJsonList('/api/v1/courses');
      final courses = [
        for (final row in rows)
          CourseSummary.fromJson(row as Map<String, dynamic>)
      ];
      for (final course in courses) {
        await _db.upsertEntity(
          entityTable: 'courses',
          entityId: course.id,
          payloadJson: jsonEncode(course.toJson()),
          serverVersion: 1,
        );
      }
      return courses;
    } on NetworkUnavailableException {
      final cached = await _db.listEntities('courses');
      return [
        for (final row in cached)
          CourseSummary.fromJson(
            jsonDecode(row['payload'] as String) as Map<String, dynamic>,
          )
      ]..sort((a, b) => a.code.compareTo(b.code));
    }
  }

  @override
  Future<List<ModuleSummary>> listModules(String courseId) async {
    try {
      final rows = await _api.getJsonList('/api/v1/courses/$courseId/modules');
      final modules = [
        for (final row in rows)
          ModuleSummary.fromJson(row as Map<String, dynamic>)
      ];
      for (final module in modules) {
        await _db.upsertEntity(
          entityTable: 'modules',
          entityId: module.id,
          payloadJson: jsonEncode(module.toJson()),
          serverVersion: 1,
        );
      }
      return modules;
    } on NetworkUnavailableException {
      final cached = await _db.listEntities('modules');
      final modules = [
        for (final row in cached)
          ModuleSummary.fromJson(
            jsonDecode(row['payload'] as String) as Map<String, dynamic>,
          )
      ].where((m) => m.courseId == courseId).toList()
        ..sort((a, b) => a.position.compareTo(b.position));
      return modules;
    }
  }

  @override
  Future<List<ResourceSummary>> listResources(String moduleId) async {
    try {
      final rows =
          await _api.getJsonList('/api/v1/modules/$moduleId/resources');
      final resources = [
        for (final row in rows)
          ResourceSummary.fromJson(row as Map<String, dynamic>)
      ];
      for (final resource in resources) {
        await _db.upsertEntity(
          entityTable: 'resources',
          entityId: resource.id,
          payloadJson: jsonEncode(resource.toJson()),
          serverVersion: resource.versionNumber,
        );
      }
      return resources;
    } on NetworkUnavailableException {
      final cached = await _db.listEntities('resources');
      return [
        for (final row in cached)
          ResourceSummary.fromJson(
            jsonDecode(row['payload'] as String) as Map<String, dynamic>,
          )
      ].where((r) => r.moduleId == moduleId).toList();
    }
  }
}
