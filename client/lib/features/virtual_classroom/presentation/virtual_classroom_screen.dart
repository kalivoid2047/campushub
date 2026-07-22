import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../domain/virtual_classroom_repository.dart';
import 'call_screen.dart';

/// Class sessions for a course (Epic E5, docs/10). "Join" always records
/// attendance (FR-VC-5); it also opens the live call when the backend's
/// LiveKit server is configured (JoinInfo.canOpenCall), and otherwise
/// confirms attendance-only via a snackbar.
class SessionsScreen extends ConsumerStatefulWidget {
  const SessionsScreen({super.key, required this.courseId, this.courseName});

  final String courseId;
  final String? courseName;

  @override
  ConsumerState<SessionsScreen> createState() => _SessionsScreenState();
}

class _SessionsScreenState extends ConsumerState<SessionsScreen> {
  List<ClassSessionSummary>? _sessions;
  String? _error;
  final _busy = <String>{};

  @override
  void initState() {
    super.initState();
    _reload();
  }

  Future<void> _reload() async {
    try {
      final sessions = await ref
          .read(virtualClassroomRepositoryProvider)
          .listSessions(widget.courseId);
      if (mounted) setState(() => _sessions = sessions);
    } catch (error) {
      if (mounted) setState(() => _error = '$error');
    }
  }

  Future<void> _createSession() async {
    final controller = TextEditingController();
    final title = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('New session'),
        content: TextField(
          controller: controller,
          autofocus: true,
          decoration: const InputDecoration(labelText: 'Title'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () =>
                Navigator.of(dialogContext).pop(controller.text.trim()),
            child: const Text('Create'),
          ),
        ],
      ),
    );
    if (title == null || title.isEmpty) return;
    await _runAction('new', () async {
      await ref
          .read(virtualClassroomRepositoryProvider)
          .createSession(widget.courseId, title);
    });
  }

  Future<void> _runAction(
      String sessionId, Future<void> Function() action) async {
    setState(() => _busy.add(sessionId));
    try {
      await action();
      await _reload();
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('$error')));
      }
    } finally {
      if (mounted) setState(() => _busy.remove(sessionId));
    }
  }

  Future<void> _join(ClassSessionSummary session) async {
    setState(() => _busy.add(session.id));
    try {
      final info =
          await ref.read(virtualClassroomRepositoryProvider).join(session.id);
      if (!mounted) return;
      if (info.canOpenCall) {
        await Navigator.of(context).push(
          MaterialPageRoute<void>(
            builder: (_) => CallScreen(
              signalingUrl: info.signalingUrl!,
              sfuToken: info.sfuToken!,
              sessionTitle: session.title,
              onLeave: () => ref
                  .read(virtualClassroomRepositoryProvider)
                  .leave(session.id),
              onStartRecording: () => ref
                  .read(virtualClassroomRepositoryProvider)
                  .startRecording(session.id),
              onStopRecording: () => ref
                  .read(virtualClassroomRepositoryProvider)
                  .stopRecording(session.id),
            ),
          ),
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              "Attendance recorded — live video isn't configured for this server yet.",
            ),
          ),
        );
      }
      await _reload();
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('$error')));
      }
    } finally {
      if (mounted) setState(() => _busy.remove(session.id));
    }
  }

  Future<void> _viewRecordings(ClassSessionSummary session) async {
    List<RecordingInfo> recordings;
    try {
      recordings = await ref
          .read(virtualClassroomRepositoryProvider)
          .listRecordings(session.id);
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('$error')));
      }
      return;
    }
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text('${session.title} — Recordings'),
        content: SizedBox(
          width: double.maxFinite,
          child: recordings.isEmpty
              ? const Text('No recordings for this session.')
              : Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    for (final recording in recordings)
                      ListTile(
                        leading: Icon(switch (recording.status) {
                          'available' => Icons.play_circle_outline,
                          'failed' => Icons.error_outline,
                          _ => Icons.hourglass_top,
                        }),
                        title: Text(_recordingSubtitle(recording)),
                        subtitle: Text(recording.status),
                        trailing: recording.downloadUrl == null
                            ? null
                            : IconButton(
                                tooltip: 'Copy download link',
                                icon: const Icon(Icons.copy),
                                onPressed: () {
                                  Clipboard.setData(
                                    ClipboardData(text: recording.downloadUrl!),
                                  );
                                  ScaffoldMessenger.of(dialogContext).showSnackBar(
                                    const SnackBar(
                                        content: Text('Link copied.')),
                                  );
                                },
                              ),
                      ),
                  ],
                ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('${widget.courseName ?? 'Course'} — Sessions'),
        actions: [
          IconButton(
            tooltip: 'Attendance report',
            icon: const Icon(Icons.fact_check_outlined),
            onPressed: () => context.push(
              '/courses/${widget.courseId}/attendance',
              extra: widget.courseName,
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () => _createSession(),
        child: const Icon(Icons.add),
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_error != null) {
      return Center(
          child:
              Padding(padding: const EdgeInsets.all(24), child: Text(_error!)));
    }
    final sessions = _sessions;
    if (sessions == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (sessions.isEmpty) {
      return const Center(
          child: Text('No sessions yet — tap + to schedule one.'));
    }
    return ListView.builder(
      itemCount: sessions.length,
      itemBuilder: (context, index) => _SessionTile(
        session: sessions[index],
        busy: _busy.contains(sessions[index].id),
        onStart: () => _runAction(
          sessions[index].id,
          () => ref
              .read(virtualClassroomRepositoryProvider)
              .start(sessions[index].id),
        ),
        onEnd: () => _runAction(
          sessions[index].id,
          () => ref
              .read(virtualClassroomRepositoryProvider)
              .end(sessions[index].id),
        ),
        onJoin: () => _join(sessions[index]),
        onViewRecordings: () => _viewRecordings(sessions[index]),
      ),
    );
  }
}

String _recordingSubtitle(RecordingInfo recording) {
  final minutes = recording.durationSeconds ~/ 60;
  final seconds = recording.durationSeconds % 60;
  final duration = '${minutes}m ${seconds.toString().padLeft(2, '0')}s';
  final sizeMb = (recording.sizeBytes / (1024 * 1024)).toStringAsFixed(1);
  return '$duration • $sizeMb MB';
}

class _SessionTile extends StatelessWidget {
  const _SessionTile({
    required this.session,
    required this.busy,
    required this.onStart,
    required this.onEnd,
    required this.onJoin,
    required this.onViewRecordings,
  });

  final ClassSessionSummary session;
  final bool busy;
  final VoidCallback onStart;
  final VoidCallback onEnd;
  final VoidCallback onJoin;
  final VoidCallback onViewRecordings;

  @override
  Widget build(BuildContext context) {
    final (chipLabel, chipColor) = switch (session.status) {
      'live' => ('live', Colors.green),
      'ended' => ('ended', Colors.grey),
      'cancelled' => ('cancelled', Colors.red),
      _ => ('scheduled', Colors.blue),
    };

    return ListTile(
      leading: const Icon(Icons.video_camera_front_outlined),
      title: Text(session.title),
      subtitle: Text(
        session.scheduledStart == null
            ? chipLabel
            : '$chipLabel • ${session.scheduledStart!.toLocal()}',
      ),
      trailing: busy
          ? const SizedBox(
              width: 20,
              height: 20,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          : Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 8,
                  height: 8,
                  margin: const EdgeInsets.only(right: 8),
                  decoration:
                      BoxDecoration(color: chipColor, shape: BoxShape.circle),
                ),
                if (session.status == 'scheduled')
                  IconButton(
                    tooltip: 'Start',
                    icon: const Icon(Icons.play_circle_outline),
                    onPressed: onStart,
                  ),
                if (session.status == 'live') ...[
                  IconButton(
                    tooltip: 'Join',
                    icon: const Icon(Icons.login),
                    onPressed: onJoin,
                  ),
                  IconButton(
                    tooltip: 'End for everyone',
                    icon: const Icon(Icons.stop_circle_outlined),
                    onPressed: onEnd,
                  ),
                ],
                if (session.status == 'ended')
                  IconButton(
                    tooltip: 'Recordings',
                    icon: const Icon(Icons.video_library_outlined),
                    onPressed: onViewRecordings,
                  ),
              ],
            ),
    );
  }
}
