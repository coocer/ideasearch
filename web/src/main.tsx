import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { createClient } from "./api/client";
import { ClientProvider } from "./api/context";
import "./styles/app.css";

const client = createClient();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ClientProvider client={client}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ClientProvider>
  </React.StrictMode>,
);
