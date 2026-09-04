import { useEffect, useRef, useState } from "react";
import { type FeedEvent, getToken } from "../api";

const MAX_EVENTS = 200;

type Status = "connecting" | "open" | "closed";

/** Subscribes to the tenant-scoped live feed. The server derives the tenant from
 *  the JWT — this hook cannot ask for another tenant's events. */
export function useLiveFeed() {
  const [events, setEvents] = useState<FeedEvent[]>([]);
  const [status, setStatus] = useState<Status>("connecting");
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let stopped = false;
    let retry: ReturnType<typeof setTimeout>;

    function connect() {
      const token = getToken();
      if (!token) return;
      const proto = location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(`${proto}://${location.host}/ws/feed?token=${token}`);
      wsRef.current = ws;
      setStatus("connecting");

      ws.onopen = () => setStatus("open");
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        if (msg.type === "snapshot") {
          setEvents(msg.events.slice(-MAX_EVENTS));
        } else if (msg.type === "request") {
          setEvents((prev) => [...prev, msg].slice(-MAX_EVENTS));
        }
      };
      ws.onclose = () => {
        setStatus("closed");
        if (!stopped) retry = setTimeout(connect, 2000);
      };
      ws.onerror = () => ws.close();
    }

    connect();
    return () => {
      stopped = true;
      clearTimeout(retry);
      wsRef.current?.close();
    };
  }, []);

  return { events, status };
}
