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

const URL = "ws://localhost:8005/ws/users";

export default function () {
  const name = `User_${__VU}_${__ITER}`;
  const email = `user_${__VU}_${__ITER}@example.com`;
  let completed = false;

  const res = ws.connect(URL, {}, function (socket) {
    let start;

    socket.on("open", function () {
      start = Date.now();
      socket.send(JSON.stringify({
        action: "create_user",
        data: { name, email },
      }));
    });

    socket.on("message", function (data) {
      wsRoundTrip.add(Date.now() - start);
      const msg = JSON.parse(data);
      completed = check(msg, {
        "user_created event": (m) => m.event === "user_created",
      });
      socket.close();
    });

    socket.setTimeout(function () {
      socket.close();
    }, 5000);
  });

  check(res, { "handshake status is 101": (r) => r && r.status === 101 });
  wsSessionCompleted.add(completed);
}
