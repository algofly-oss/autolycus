import React from "react";
import io from "socket.io-client";

const socket = io({
  transports: ["websocket"],
});
const SocketContext = React.createContext();

export { socket, SocketContext };
