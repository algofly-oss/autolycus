import React from "react";
import io from "socket.io-client";

const socket = null; // TODO: enable this when we have a socket server
// const socket = io({
//   transports: ["websocket"],
// });
const SocketContext = React.createContext();

export { socket, SocketContext };
