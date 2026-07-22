import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../data/message_socket.dart';
import '../domain/communication_repository.dart';

/// Announcements tab (docs/07-ui-ux.md section 4: dashboard feed).
class AnnouncementsTab extends ConsumerWidget {
  const AnnouncementsTab({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final repository = ref.watch(communicationRepositoryProvider);
    return FutureBuilder<List<AnnouncementSummary>>(
      future: repository.listAnnouncements(),
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return Center(child: Text('${snapshot.error}'));
        }
        final announcements = snapshot.data ?? const [];
        if (announcements.isEmpty) {
          return const Center(child: Text('No announcements.'));
        }
        return ListView.builder(
          itemCount: announcements.length,
          itemBuilder: (context, index) {
            final announcement = announcements[index];
            return Card(
              margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              child: ListTile(
                leading: Icon(
                  announcement.scope == 'institution'
                      ? Icons.campaign_outlined
                      : Icons.class_outlined,
                ),
                title: Text(announcement.title),
                subtitle: Text(
                  announcement.body,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            );
          },
        );
      },
    );
  }
}

/// Message thread for a course channel or DM (docs/06 section 6/7): initial
/// history over REST, live delivery over the WebSocket (docs/06 section 7),
/// paginate-older on demand. Tapping another sender's bubble starts a DM
/// with them, satisfying the "message a classmate" flow without needing a
/// separate user directory screen.
class MessageThreadScreen extends ConsumerStatefulWidget {
  const MessageThreadScreen({super.key, required this.channelId, this.title});

  final String channelId;
  final String? title;

  @override
  ConsumerState<MessageThreadScreen> createState() =>
      _MessageThreadScreenState();
}

class _MessageThreadScreenState extends ConsumerState<MessageThreadScreen> {
  final _messages = <MessageItem>[];
  final _seenIds = <String>{};
  final _bodyController = TextEditingController();
  String? _nextCursor;
  bool _hasMore = false;
  bool _loadingInitial = true;
  bool _loadingMore = false;
  bool _sending = false;
  String? _currentUserId;

  MessageSocket? _socket;

  @override
  void initState() {
    super.initState();
    _loadInitial();
    _connectSocket();
    ref.read(authRepositoryProvider).currentUser().then((profile) {
      if (mounted) setState(() => _currentUserId = profile.id);
    });
  }

  @override
  void dispose() {
    _socket?.dispose();
    _bodyController.dispose();
    super.dispose();
  }

  Future<void> _loadInitial() async {
    final repository = ref.read(communicationRepositoryProvider);
    try {
      final page = await repository.listMessages(widget.channelId);
      if (!mounted) return;
      setState(() {
        _messages.addAll(page.messages);
        _seenIds.addAll(page.messages.map((m) => m.id));
        _nextCursor = page.nextCursor;
        _hasMore = page.hasMore;
        _loadingInitial = false;
      });
    } catch (error) {
      if (mounted) {
        setState(() => _loadingInitial = false);
        _showError('$error');
      }
    }
  }

  Future<void> _loadMore() async {
    if (!_hasMore || _loadingMore) return;
    setState(() => _loadingMore = true);
    try {
      final repository = ref.read(communicationRepositoryProvider);
      final page =
          await repository.listMessages(widget.channelId, before: _nextCursor);
      if (!mounted) return;
      setState(() {
        for (final message in page.messages) {
          if (_seenIds.add(message.id)) _messages.add(message);
        }
        _nextCursor = page.nextCursor;
        _hasMore = page.hasMore;
      });
    } finally {
      if (mounted) setState(() => _loadingMore = false);
    }
  }

  void _connectSocket() {
    final socket = MessageSocket(ref.read(apiClientProvider));
    _socket = socket;
    socket.connect(widget.channelId);
    socket.messages.listen((message) {
      if (!mounted || !_seenIds.add(message.id)) return;
      setState(() => _messages.insert(0, message));
    });
  }

  Future<void> _send() async {
    final body = _bodyController.text.trim();
    if (body.isEmpty || _sending) return;
    setState(() => _sending = true);
    try {
      final repository = ref.read(communicationRepositoryProvider);
      final sent = await repository.sendMessage(
        widget.channelId,
        body,
        currentUserId: _currentUserId ?? '',
      );
      if (!mounted) return;
      if (sent.pending) {
        _showError('Saved — will send once you\'re back online.');
      }
      if (_seenIds.add(sent.id)) {
        setState(() {
          _messages.insert(0, sent);
          _bodyController.clear();
        });
      } else {
        _bodyController.clear();
      }
    } catch (error) {
      _showError('$error');
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _startDmWith(String recipientId) async {
    if (recipientId == _currentUserId) return;
    try {
      final channel = await ref
          .read(communicationRepositoryProvider)
          .getOrCreateDm(recipientId);
      if (mounted) {
        context.push('/channels/${channel.id}', extra: 'Direct message');
      }
    } catch (error) {
      _showError('$error');
    }
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.title ?? 'Discussion')),
      body: Column(
        children: [
          Expanded(
            child: _loadingInitial
                ? const Center(child: CircularProgressIndicator())
                : _messages.isEmpty
                    ? const Center(child: Text('No messages yet — say hello.'))
                    : ListView.builder(
                        reverse: true,
                        itemCount: _messages.length + (_hasMore ? 1 : 0),
                        itemBuilder: (context, index) {
                          if (index == _messages.length) {
                            return Center(
                              child: Padding(
                                padding: const EdgeInsets.all(12),
                                child: _loadingMore
                                    ? const CircularProgressIndicator()
                                    : TextButton(
                                        onPressed: _loadMore,
                                        child:
                                            const Text('Load earlier messages'),
                                      ),
                              ),
                            );
                          }
                          final message = _messages[index];
                          final isMine = message.pending ||
                              message.senderId == _currentUserId;
                          return _MessageBubble(
                            message: message,
                            isMine: isMine,
                            onTapAvatar: isMine
                                ? null
                                : () => _startDmWith(message.senderId),
                          );
                        },
                      ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(8),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _bodyController,
                      decoration: const InputDecoration(
                        hintText: 'Message',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                      onSubmitted: (_) => _send(),
                    ),
                  ),
                  const SizedBox(width: 8),
                  IconButton.filled(
                    onPressed: _sending ? null : _send,
                    icon: _sending
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.send),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({
    required this.message,
    required this.isMine,
    this.onTapAvatar,
  });

  final MessageItem message;
  final bool isMine;
  final VoidCallback? onTapAvatar;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      child: Row(
        mainAxisAlignment:
            isMine ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          if (!isMine)
            InkWell(
              onTap: onTapAvatar,
              customBorder: const CircleBorder(),
              child: const Padding(
                padding: EdgeInsets.only(right: 6),
                child: CircleAvatar(
                    radius: 14, child: Icon(Icons.person, size: 16)),
              ),
            ),
          Flexible(
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: isMine
                    ? colorScheme.primaryContainer
                    : colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(message.body),
                  if (message.pending)
                    Padding(
                      padding: const EdgeInsets.only(top: 2),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            Icons.schedule,
                            size: 12,
                            color: colorScheme.onPrimaryContainer
                                .withValues(alpha: 0.7),
                          ),
                          const SizedBox(width: 4),
                          Text(
                            'Sending…',
                            style: TextStyle(
                              fontSize: 11,
                              color: colorScheme.onPrimaryContainer
                                  .withValues(alpha: 0.7),
                            ),
                          ),
                        ],
                      ),
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
