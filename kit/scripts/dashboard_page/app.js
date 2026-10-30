"use strict";
const lanes = {};
document.querySelectorAll("section[data-lane]").forEach(function (section) {
  lanes[section.dataset.lane] = section.querySelector("ul");
});

function line(parent, text) {
  const small = document.createElement("small");
  small.textContent = text;
  parent.appendChild(small);
}

function card(piece) {
  const item = document.createElement("li");
  const title = document.createElement("strong");
  title.textContent = "#" + piece.number + " " + piece.title;
  item.appendChild(title);
  line(item, piece.stage + (piece.attempt ? ", attempt " + piece.attempt : ""));
  if (piece.waiting_on.length) {
    line(item, "waiting on " + piece.waiting_on.map(function (n) { return "#" + n; }).join(", "));
  }
  if (piece.handback_reason) {
    line(item, "handed back: " + piece.handback_reason);
  }
  if (piece.last_event) {
    line(item, piece.last_event + (piece.since ? " at " + piece.since : ""));
  }
  if (piece.pr_url && /^https?:\/\//.test(piece.pr_url)) {
    const link = document.createElement("a");
    link.href = piece.pr_url;
    link.textContent = "Pull request";
    item.appendChild(link);
  }
  return item;
}

function show(snapshot) {
  document.getElementById("run").textContent = "Run: " + snapshot.run.status +
    (snapshot.run.started ? ", started " + snapshot.run.started : "");
  const notices = document.getElementById("notices");
  notices.replaceChildren();
  snapshot.notices.forEach(function (text) {
    const note = document.createElement("p");
    note.setAttribute("role", "alert");
    note.textContent = text;
    notices.appendChild(note);
  });
  Object.keys(lanes).forEach(function (name) {
    lanes[name].replaceChildren();
  });
  snapshot.pieces.forEach(function (piece) {
    if (lanes[piece.lane]) {
      lanes[piece.lane].appendChild(card(piece));
    }
  });
}

const status = document.getElementById("connection");
const source = new EventSource("/api/events");
source.onmessage = function (event) {
  status.textContent = "";
  show(JSON.parse(event.data));
};
source.onerror = function () {
  status.textContent = "Connection lost. Reconnecting.";
};
