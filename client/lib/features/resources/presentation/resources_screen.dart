import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../data/download_manager.dart';
import '../domain/resources_repository.dart';

/// Courses tab: the caller's enrolled courses (docs/07-ui-ux.md section 1).
class CoursesTab extends ConsumerWidget {
  const CoursesTab({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final repository = ref.watch(catalogRepositoryProvider);
    return FutureBuilder<List<CourseSummary>>(
      future: repository.listCourses(),
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return _ErrorRetry(message: '${snapshot.error}');
        }
        final courses = snapshot.data ?? const [];
        if (courses.isEmpty) {
          return const Center(child: Text('No courses yet.'));
        }
        return ListView.builder(
          itemCount: courses.length,
          itemBuilder: (context, index) {
            final course = courses[index];
            return ListTile(
              leading: const Icon(Icons.school_outlined),
              title: Text(course.name),
              subtitle: Text('${course.code} • ${course.term}'),
              onTap: () => context.push(
                '/courses/${course.id}',
                extra: course.name,
              ),
            );
          },
        );
      },
    );
  }
}

/// Course detail: content modules list.
class CourseDetailScreen extends ConsumerWidget {
  const CourseDetailScreen(
      {super.key, required this.courseId, this.courseName});

  final String courseId;
  final String? courseName;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final repository = ref.watch(catalogRepositoryProvider);
    return Scaffold(
      appBar: AppBar(
        title: Text(courseName ?? 'Course'),
        actions: [
          IconButton(
            tooltip: 'Discussion',
            icon: const Icon(Icons.forum_outlined),
            onPressed: () async {
              try {
                final channel = await ref
                    .read(communicationRepositoryProvider)
                    .getCourseChannel(courseId);
                if (context.mounted) {
                  context.push(
                    '/channels/${channel.id}',
                    extra: courseName == null
                        ? 'Discussion'
                        : '$courseName discussion',
                  );
                }
              } catch (error) {
                if (context.mounted) {
                  ScaffoldMessenger.of(context)
                      .showSnackBar(SnackBar(content: Text('$error')));
                }
              }
            },
          ),
          IconButton(
            tooltip: 'Assignments',
            icon: const Icon(Icons.assignment_outlined),
            onPressed: () => context.push(
              '/courses/$courseId/assignments',
              extra: courseName,
            ),
          ),
          IconButton(
            tooltip: 'Sessions',
            icon: const Icon(Icons.video_camera_front_outlined),
            onPressed: () => context.push(
              '/courses/$courseId/sessions',
              extra: courseName,
            ),
          ),
        ],
      ),
      body: FutureBuilder<List<ModuleSummary>>(
        future: repository.listModules(courseId),
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return _ErrorRetry(message: '${snapshot.error}');
          }
          final modules = snapshot.data ?? const [];
          if (modules.isEmpty) {
            return const Center(child: Text('No modules published yet.'));
          }
          return ListView.builder(
            itemCount: modules.length,
            itemBuilder: (context, index) {
              final module = modules[index];
              return ListTile(
                leading: const Icon(Icons.folder_outlined),
                title: Text(module.title),
                onTap: () => context.push(
                  '/modules/${module.id}',
                  extra: module.title,
                ),
              );
            },
          );
        },
      ),
    );
  }
}

/// Module detail: resources with type/size metadata.
class ModuleResourcesScreen extends ConsumerWidget {
  const ModuleResourcesScreen(
      {super.key, required this.moduleId, this.moduleTitle});

  final String moduleId;
  final String? moduleTitle;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final repository = ref.watch(catalogRepositoryProvider);
    return Scaffold(
      appBar: AppBar(title: Text(moduleTitle ?? 'Module')),
      body: FutureBuilder<List<ResourceSummary>>(
        future: repository.listResources(moduleId),
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return _ErrorRetry(message: '${snapshot.error}');
          }
          final resources = snapshot.data ?? const [];
          if (resources.isEmpty) {
            return const Center(child: Text('No resources in this module.'));
          }
          return ListView.builder(
            itemCount: resources.length,
            itemBuilder: (context, index) =>
                _ResourceTile(resource: resources[index]),
          );
        },
      ),
    );
  }
}

/// A resource row with real offline download state (docs/09 section 5,
/// docs/07-ui-ux.md section 3.4): tap the trailing icon to download; once
/// downloaded, the same control removes the local copy.
class _ResourceTile extends ConsumerStatefulWidget {
  const _ResourceTile({required this.resource});

  final ResourceSummary resource;

  @override
  ConsumerState<_ResourceTile> createState() => _ResourceTileState();
}

class _ResourceTileState extends ConsumerState<_ResourceTile> {
  DownloadInfo? _info;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _refreshStatus();
  }

  Future<void> _refreshStatus() async {
    final manager = ref.read(downloadManagerProvider);
    final info = await manager.status(
      widget.resource.id,
      currentVersionSize: widget.resource.sizeBytes,
    );
    if (mounted) setState(() => _info = info);
  }

  Future<void> _toggle() async {
    final manager = ref.read(downloadManagerProvider);
    setState(() => _busy = true);
    try {
      if (_info?.state == DownloadState.downloaded) {
        await manager.removeDownload(widget.resource.id);
      } else {
        await manager.download(widget.resource.id);
      }
      await _refreshStatus();
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Download failed: $error')),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = _info?.state ?? DownloadState.notDownloaded;
    final subtitle = switch (state) {
      DownloadState.downloaded =>
        'v${widget.resource.versionNumber} • ${_formatBytes(widget.resource.sizeBytes)} • Downloaded',
      DownloadState.staleVersionAvailable =>
        'v${widget.resource.versionNumber} • ${_formatBytes(widget.resource.sizeBytes)} • Update available',
      DownloadState.notDownloaded =>
        'v${widget.resource.versionNumber} • ${_formatBytes(widget.resource.sizeBytes)}',
    };

    return ListTile(
      leading: Icon(_iconFor(widget.resource.type)),
      title: Text(widget.resource.title),
      subtitle: Text(subtitle),
      trailing: _busy
          ? const SizedBox(
              width: 20,
              height: 20,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          : IconButton(
              tooltip: state == DownloadState.downloaded
                  ? 'Remove offline copy'
                  : 'Download for offline use',
              icon: Icon(switch (state) {
                DownloadState.downloaded => Icons.offline_pin,
                DownloadState.staleVersionAvailable =>
                  Icons.download_for_offline,
                DownloadState.notDownloaded => Icons.download_outlined,
              }),
              onPressed: _toggle,
            ),
    );
  }
}

IconData _iconFor(String type) => switch (type) {
      'slide' => Icons.slideshow_outlined,
      'video' => Icons.play_circle_outline,
      'link' => Icons.link,
      _ => Icons.description_outlined,
    };

String _formatBytes(int bytes) {
  if (bytes >= 1024 * 1024) {
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }
  if (bytes >= 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
  return '$bytes B';
}

class _ErrorRetry extends StatelessWidget {
  const _ErrorRetry({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Text(message, textAlign: TextAlign.center),
      ),
    );
  }
}
