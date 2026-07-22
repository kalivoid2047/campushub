import 'package:flutter/material.dart';
import 'package:livekit_client/livekit_client.dart' as lk;

/// Live call UI (docs/10-virtual-classroom.md): connects directly to the
/// LiveKit room using the token minted by `POST /sessions/{id}/join`
/// (backend `VirtualClassroomService._media_join_info`). CampusHub's own
/// backend does not relay media or signaling — this widget talks to LiveKit
/// directly, which is the standard LiveKit client integration pattern.
class CallScreen extends StatefulWidget {
  const CallScreen({
    super.key,
    required this.signalingUrl,
    required this.sfuToken,
    required this.sessionTitle,
    required this.onLeave,
  });

  final String signalingUrl;
  final String sfuToken;
  final String sessionTitle;

  /// Called once, before popping, to record the leave server-side
  /// (closes the attendance window — FR-VC-5/FR-ATT-1).
  final Future<void> Function() onLeave;

  @override
  State<CallScreen> createState() => _CallScreenState();
}

class _CallScreenState extends State<CallScreen> {
  final _room = lk.Room();
  lk.EventsListener<lk.RoomEvent>? _listener;
  bool _connecting = true;
  bool _leaving = false;
  bool _micEnabled = true;
  bool _cameraEnabled = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _connect();
  }

  Future<void> _connect() async {
    try {
      await _room.connect(widget.signalingUrl, widget.sfuToken);
      await _room.localParticipant?.setMicrophoneEnabled(true);
      await _room.localParticipant?.setCameraEnabled(true);
      _listener = _room.createListener();
      // Any room/participant/track change re-renders the tile grid — simpler
      // and safe (idempotent setState) rather than tracking each event kind.
      _listener!.listen((_) {
        if (mounted) setState(() {});
      });
      if (mounted) setState(() => _connecting = false);
    } catch (error) {
      if (mounted) {
        setState(() {
          _error = '$error';
          _connecting = false;
        });
      }
    }
  }

  Future<void> _leave() async {
    if (_leaving) return;
    setState(() => _leaving = true);
    await _listener?.dispose();
    await _room.disconnect();
    try {
      await widget.onLeave();
    } catch (_) {
      // The room connection is already torn down; a failed leave-record
      // call is not worth blocking the user from exiting the call UI.
    }
    if (mounted) Navigator.of(context).pop();
  }

  @override
  void dispose() {
    _listener?.dispose();
    _room.dispose();
    super.dispose();
  }

  Future<void> _toggleMic() async {
    final next = !_micEnabled;
    await _room.localParticipant?.setMicrophoneEnabled(next);
    if (mounted) setState(() => _micEnabled = next);
  }

  Future<void> _toggleCamera() async {
    final next = !_cameraEnabled;
    await _room.localParticipant?.setCameraEnabled(next);
    if (mounted) setState(() => _cameraEnabled = next);
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) async {
        if (!didPop) await _leave();
      },
      child: Scaffold(
        backgroundColor: Colors.black,
        appBar: AppBar(
          title: Text(widget.sessionTitle),
          backgroundColor: Colors.black87,
          foregroundColor: Colors.white,
        ),
        body: _connecting
            ? const Center(child: CircularProgressIndicator())
            : _error != null
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Text(_error!,
                          style: const TextStyle(color: Colors.white)),
                    ),
                  )
                : _buildGrid(),
        bottomNavigationBar: _connecting || _error != null
            ? null
            : Container(
                color: Colors.black87,
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    IconButton(
                      tooltip: _micEnabled ? 'Mute' : 'Unmute',
                      icon: Icon(
                        _micEnabled ? Icons.mic : Icons.mic_off,
                        color: Colors.white,
                      ),
                      onPressed: _toggleMic,
                    ),
                    const SizedBox(width: 16),
                    IconButton(
                      tooltip: _cameraEnabled ? 'Stop camera' : 'Start camera',
                      icon: Icon(
                        _cameraEnabled ? Icons.videocam : Icons.videocam_off,
                        color: Colors.white,
                      ),
                      onPressed: _toggleCamera,
                    ),
                    const SizedBox(width: 16),
                    IconButton(
                      tooltip: 'Leave',
                      icon: _leaving
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(
                                  strokeWidth: 2, color: Colors.white),
                            )
                          : const Icon(Icons.call_end, color: Colors.red),
                      onPressed: _leaving ? null : _leave,
                    ),
                  ],
                ),
              ),
      ),
    );
  }

  Widget _buildGrid() {
    final tiles = <Widget>[
      _ParticipantTile(participant: _room.localParticipant, label: 'You'),
      for (final participant in _room.remoteParticipants.values)
        _ParticipantTile(participant: participant, label: participant.identity),
    ];
    return GridView.count(
      crossAxisCount: tiles.length <= 2 ? 1 : 2,
      children: tiles,
    );
  }
}

class _ParticipantTile extends StatelessWidget {
  const _ParticipantTile({required this.participant, required this.label});

  final lk.Participant? participant;
  final String label;

  @override
  Widget build(BuildContext context) {
    final publications = participant?.videoTrackPublications ?? const [];
    final track = publications.isNotEmpty ? publications.first.track : null;

    return Container(
      margin: const EdgeInsets.all(4),
      color: Colors.grey.shade900,
      child: Stack(
        fit: StackFit.expand,
        children: [
          if (track is lk.VideoTrack)
            lk.VideoTrackRenderer(track)
          else
            const Center(
                child: Icon(Icons.person, size: 48, color: Colors.white54)),
          Positioned(
            left: 8,
            bottom: 8,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              color: Colors.black45,
              child: Text(label,
                  style: const TextStyle(color: Colors.white, fontSize: 12)),
            ),
          ),
        ],
      ),
    );
  }
}
