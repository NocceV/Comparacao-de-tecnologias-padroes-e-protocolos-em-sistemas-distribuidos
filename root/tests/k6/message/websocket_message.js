import ws from "k6/ws";
import { check } from "k6";
import { Trend, Rate } from "k6/metrics";

export const options = {
  stages: [
    { duration: "30s", target: 50 },
    { duration: "1m", target: 50 },
    { duration: "20s", target: 0 },
  ],
  thresholds: {
    ws_round_trip_duration: ["p(95)<200"],
    ws_session_completed_rate: ["rate>0.99"],
  },
};

const wsRoundTrip = new Trend("ws_round_trip_duration", true);
const wsSessionCompleted = new Rate("ws_session_completed_rate");

const URL = "ws://localhost:8015/ws/messages";

export default function () {
  const user = `User_${__VU}_${__ITER}`;
  const content = `Mensagem via K6 - ${__VU}_${__ITER}`;
  let completed = false;

  const res = ws.connect(URL, {}, function (socket) {
    let start;

    socket.on("open", function () {
      start = Date.now();
      socket.send(JSON.stringify({
        action: "send_message",
        data: { user, content },
      }));
    });

    socket.on("message", function (data) {
      const msg = JSON.parse(data);
      if (msg.event === "message_created" && msg.data && msg.data.content === content) {
        wsRoundTrip.add(Date.now() - start);
        completed = check(msg, {
          "message_created event": (m) => m.event === "message_created",
        });
        socket.close();
      }
    });

    socket.setTimeout(function () {
      socket.close();
    }, 5000);
  });

  check(res, { "handshake status is 101": (r) => r && r.status === 101 });
  wsSessionCompleted.add(completed);
}
