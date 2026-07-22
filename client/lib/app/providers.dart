import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/network/api_client.dart';
import '../core/storage/local_database.dart';
import '../core/storage/secure_storage.dart';
import '../core/sync/sync_engine.dart';
import '../core/sync/sync_scheduler.dart';
import '../features/assignments/data/assignments_repository_impl.dart';
import '../features/assignments/domain/assignments_repository.dart';
import '../features/attendance/data/attendance_repository_impl.dart';
import '../features/attendance/domain/attendance_repository.dart';
import '../features/auth/data/auth_repository_impl.dart';
import '../features/auth/domain/auth_repository.dart';
import '../features/communication/data/communication_repository_impl.dart';
import '../features/communication/domain/communication_repository.dart';
import '../features/resources/data/download_manager.dart';
import '../features/resources/data/resources_repository_impl.dart';
import '../features/resources/domain/resources_repository.dart';
import '../features/search/data/search_repository_impl.dart';
import '../features/search/domain/search_repository.dart';
import '../features/tenancy_admin/data/tenancy_admin_repository_impl.dart';
import '../features/tenancy_admin/domain/tenancy_admin_repository.dart';
import '../features/virtual_classroom/data/virtual_classroom_repository_impl.dart';
import '../features/virtual_classroom/domain/virtual_classroom_repository.dart';

/// Composition root (docs/16-folder-structure.md section 2).
/// Tests override these providers with fakes.

const apiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://localhost:8000',
);

final secureStoreProvider =
    Provider<SecureStore>((ref) => PlatformSecureStore());

/// Builds the ApiClient + AuthRepositoryImpl pair. AuthRepositoryImpl is both
/// the AuthRepository and the client's TokenProvider; late binding breaks the
/// construction cycle (docs/06 section 2 refresh flow).
final _authWiringProvider = Provider<(ApiClient, AuthRepositoryImpl)>((ref) {
  final client = ApiClient(apiBaseUrl);
  final auth = AuthRepositoryImpl(client, ref.watch(secureStoreProvider));
  client.tokenProvider = auth;
  return (client, auth);
});

final apiClientProvider = Provider<ApiClient>(
  (ref) => ref.watch(_authWiringProvider).$1,
);

final authRepositoryProvider = Provider<AuthRepository>(
  (ref) => ref.watch(_authWiringProvider).$2,
);

/// Opened in main() before runApp and injected via ProviderScope override —
/// reads must never race the schema creation.
final localDatabaseProvider = Provider<LocalDatabase>(
  (ref) => throw UnimplementedError(
      'localDatabaseProvider is overridden at startup'),
);

final catalogRepositoryProvider = Provider<CatalogRepository>(
  (ref) => CatalogRepositoryImpl(
    ref.watch(apiClientProvider),
    ref.watch(localDatabaseProvider),
  ),
);

final communicationRepositoryProvider = Provider<CommunicationRepository>(
  (ref) => CommunicationRepositoryImpl(
    ref.watch(apiClientProvider),
    ref.watch(localDatabaseProvider),
  ),
);

final assignmentsRepositoryProvider = Provider<AssignmentsRepository>(
  (ref) => AssignmentsRepositoryImpl(
    ref.watch(apiClientProvider),
    ref.watch(localDatabaseProvider),
  ),
);

final searchRepositoryProvider = Provider<SearchRepository>(
  (ref) => SearchRepositoryImpl(ref.watch(apiClientProvider)),
);

final virtualClassroomRepositoryProvider = Provider<VirtualClassroomRepository>(
  (ref) => VirtualClassroomRepositoryImpl(ref.watch(apiClientProvider)),
);

final attendanceRepositoryProvider = Provider<AttendanceRepository>(
  (ref) => AttendanceRepositoryImpl(ref.watch(apiClientProvider)),
);

final tenancyAdminRepositoryProvider = Provider<TenancyAdminRepository>(
  (ref) => TenancyAdminRepositoryImpl(ref.watch(apiClientProvider)),
);

/// Resolved in main() (path_provider is async) and injected via
/// ProviderScope override, mirroring localDatabaseProvider.
final downloadsDirectoryProvider = Provider<Directory>(
  (ref) => throw UnimplementedError(
      'downloadsDirectoryProvider is overridden at startup'),
);

final downloadManagerProvider = Provider<DownloadManager>(
  (ref) => DownloadManager(
    ref.watch(apiClientProvider),
    ref.watch(localDatabaseProvider),
    ref.watch(downloadsDirectoryProvider),
  ),
);

final syncEngineProvider = Provider<SyncEngine>(
  (ref) => SyncEngine(
    ref.watch(apiClientProvider),
    ref.watch(localDatabaseProvider),
  ),
);

/// Last sync outcome, surfaced by the app-bar status chip (FR-SYNC-4).
final lastSyncResultProvider = StateProvider<SyncResult?>((ref) => null);

/// One scheduler per app session: started when the signed-in shell mounts,
/// disposed when it unmounts (docs/09 section 4 background sync). Kept as a
/// provider (rather than a raw field in the widget) so any screen can call
/// `ref.read(syncSchedulerProvider).runNow()`.
final syncSchedulerProvider = Provider<SyncScheduler>((ref) {
  final scheduler =
      SyncScheduler(() => ref.read(syncEngineProvider).runSyncCycle());
  ref.onDispose(scheduler.dispose);
  return scheduler;
});
