#pragma once
// Push-to-talk: half-duplex turn control. Student speaks only while TTS is silent
// -> clean turn segmentation (validity) AND avoids echo on the no-AEC board.

#include <functional>

namespace aivmt {

class PushToTalk {
 public:
  using Handler = std::function<void(bool pressed)>;  // true=press(start turn), false=release

  explicit PushToTalk(int gpio);
  void Init();                 // configure GPIO + ISR/debounce
  void SetHandler(Handler h);  // forwarded to SpSession as PttPress/PttRelease

 private:
  int gpio_;
  Handler handler_;
};

}  // namespace aivmt
