/// Communication domain (client side of Epic E3).
library;

class AnnouncementSummary {
  const AnnouncementSummary({
    required this.id,
    required this.scope,
    required this.title,
    required this.body,
    required this.createdAt,
  });

  final String id;
  final String scope;
  final String title;
  final String body;
  final DateTime createdAt;

  factory AnnouncementSummary.fromJson(Map<String, dynamic> json) =>
      AnnouncementSummary(
        id: json['id'] as String,
        scope: json['scope'] as String,
        title: json['title'] as String,
        body: json['body'] as String,
        createdAt: DateTime.parse(json['created_at'] as String),
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'scope': scope,
        'title': title,
        'body': body,
        'created_at': createdAt.toIso8601String(),
      };
}

class ChannelSummary {
  const ChannelSummary({
    required this.id,
    required this.type,
    this.courseId,
    this.name,
  });

  final String id;
  final String type; // "course" | "dm"
  final String? courseId;
  final String? name;

  factory ChannelSummary.fromJson(Map<String, dynamic> json) => ChannelSummary(
        id: json['id'] as String,
        type: json['type'] as String,
        courseId: json['course_id'] as String?,
        name: json['name'] as String?,
      );
}

class MessageItem {
  const MessageItem({
    required this.id,
    required this.channelId,
    required this.senderId,
    required this.body,
    required this.createdAt,
    this.pending = false,
  });

  final String id;
  final String channelId;
  final String senderId;
  final String body;
  final DateTime createdAt;

  /// True for a message composed offline and queued locally — it hasn't
  /// been confirmed by the server yet (docs/09 section 4, FR-COM-4). The
  /// thread UI shows this distinctly (e.g. "sending…").
  final bool pending;

  factory MessageItem.fromJson(Map<String, dynamic> json) => MessageItem(
        id: json['id'] as String,
        channelId: json['channel_id'] as String,
        senderId: json['sender_id'] as String,
        body: json['body'] as String,
        createdAt: DateTime.parse(json['created_at'] as String),
      );

  /// Constructs from a live WebSocket "message.created" event, which uses
  /// the same field names as the REST response (docs/06 section 7).
  factory MessageItem.fromSocketEvent(Map<String, dynamic> json) =>
      MessageItem.fromJson(json);
}

class MessagePageResult {
  const MessagePageResult({
    required this.messages,
    required this.nextCursor,
    required this.hasMore,
  });

  final List<MessageItem> messages; // newest-first, per docs/06 section 6
  final String? nextCursor;
  final bool hasMore;
}

abstract class CommunicationRepository {
  /// Network-first with cache fallback (docs/09 section 7).
  Future<List<AnnouncementSummary>> listAnnouncements();

  /// Gets or lazily creates the discussion channel for a course
  /// (docs/06 section 6). Requires connectivity — channels are not cached.
  Future<ChannelSummary> getCourseChannel(String courseId);

  /// Gets or creates a direct-message channel with [recipientId].
  Future<ChannelSummary> getOrCreateDm(String recipientId);

  /// Newest-first message page. [before] is an ISO-8601 cursor from a
  /// previous page's [MessagePageResult.nextCursor].
  Future<MessagePageResult> listMessages(String channelId, {String? before});

  /// Sends a message. Online: delivered immediately, returns the server's
  /// canonical record. Offline: queued to the local sync queue (registered
  /// backend-side as the "messages" sync entity, mirroring submissions) and
  /// returns an optimistic [MessageItem] with [MessageItem.pending] set —
  /// it carries the client-generated id, not the eventual server id, so the
  /// thread may show a duplicate if delta-pull later surfaces the synced
  /// copy before the next full refresh reconciles them.
  Future<MessageItem> sendMessage(
    String channelId,
    String body, {
    required String currentUserId,
  });
}
