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

const ticked = new Set();
const token = document.querySelector("meta[name=loop-token]").content;
const button = document.getElementById("run-button");
const answer = document.getElementById("answer");
let busy = false;

function refreshButton() {
  button.disabled = busy || ticked.size === 0;
}

function say(text) {
  const note = document.createElement("p");
  note.textContent = text;
  answer.appendChild(note);
}

function tickBox(piece) {
  const box = document.createElement("input");
  box.type = "checkbox";
  box.checked = ticked.has(piece.number);
  box.disabled = piece.needs_services.length > 0;
  box.setAttribute("aria-label", "Build piece " + piece.number);
  box.onchange = function () {
    if (box.checked) { ticked.add(piece.number); } else { ticked.delete(piece.number); }
    refreshButton();
  };
  return box;
}

function card(piece) {
  const item = document.createElement("li");
  const title = document.createElement("strong");
  title.textContent = "#" + piece.number + " " + piece.title;
  if (piece.lane === "shaped") {
    item.appendChild(tickBox(piece));
  }
  item.appendChild(title);
  if (piece.needs_services && piece.needs_services.length) {
    line(item, "needs services (" + piece.needs_services.join(", ") + "), so it cannot walk away");
  }
  if (piece.depends_on && piece.depends_on.length) {
    line(item, "depends on " + piece.depends_on.map(function (n) { return "#" + n; }).join(", "));
  }
  line(item, piece.stage + (piece.attempt ? ", attempt " + piece.attempt : ""));
  if (piece.waiting_on.length) {
    line(item, "waiting on " + piece.waiting_on.map(function (n) { return "#" + n; }).join(", "));
  }
  if (piece.question_blockers) {
    line(item, "held by an open question on " + piece.question_blockers.map(function (n) { return "#" + n; }).join(", "));
  }
  if (piece.question) {
    item.appendChild(questionForm(piece));
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

const drafts = {};

function questionForm(piece) {
  const asked = piece.question;
  const form = document.createElement("form");
  line(form, "Question: " + asked.text);
  const advice = asked.recommendation;
  if (advice) {
    line(form, "Recommended: answer and " + advice.path + (advice.because ? " (" + advice.because + ")" : ""));
  }
  if (asked.answered) {
    line(form, "Answered. Make the piece ready again when its checks pass.");
    return form;
  }
  const box = document.createElement("textarea");
  box.setAttribute("aria-label", "Answer for piece " + piece.number);
  box.maxLength = 2000;
  box.value = drafts[piece.number] || "";
  box.oninput = function () { drafts[piece.number] = box.value; };
  form.appendChild(box);
  ["retry", "reshape"].forEach(function (path) {
    const send = document.createElement("button");
    send.type = "button";
    send.textContent = "Answer and " + path + (advice && advice.path === path ? " (recommended)" : "");
    send.onclick = function () {
      post("/api/answer", {piece: piece.number, text: box.value, path: path}).then(function (response) {
        return response.json().then(function (data) { return {ok: response.ok, data: data}; });
      }).then(function (result) {
        if (result.ok) { delete drafts[piece.number]; }
        answer.replaceChildren();
        say(result.ok ? "Piece " + piece.number + ": " + result.data.result
                      : "Not answered: " + result.data.error + (result.data.next ? " Next: " + result.data.next : ""));
      }).catch(function () { say("Could not reach the dashboard server."); });
    };
    form.appendChild(send);
  });
  return form;
}

const seen = new Set();
let firstLook = true;

function post(path, body) {
  return fetch(path, {method: "POST",
    headers: {"Content-Type": "application/json", "X-Loop-Token": token},
    body: JSON.stringify(body)});
}

function showNotes(snapshot) {
  const list = document.getElementById("note-list");
  const toast = document.getElementById("toast");
  list.replaceChildren();
  (snapshot.notifications || []).forEach(function (note) {
    const key = note.kind + note.piece + note.message + note.time;
    const item = document.createElement("li");
    item.textContent = note.message + (note.time ? " (" + note.time + ")" : "");
    list.appendChild(item);
    if (!seen.has(key)) {
      seen.add(key);
      if (!firstLook) { toast.textContent = note.message; }
    }
  });
  firstLook = false;
  const notify = (snapshot.preferences || {}).notify || {};
  document.getElementById("pref-macos").checked = notify.macos === true;
  document.getElementById("pref-sound").value = notify.sound || "";
}

function savePrefs() {
  post("/api/preferences", {notify: {
    macos: document.getElementById("pref-macos").checked,
    sound: document.getElementById("pref-sound").value || null}});
}
document.getElementById("pref-macos").onchange = savePrefs;
document.getElementById("pref-sound").onchange = savePrefs;

function show(snapshot) {
  showNotes(snapshot);
  busy = snapshot.run.starting || snapshot.run.status === "running";
  refreshButton();
  document.getElementById("run").textContent = "Run: " +
    (snapshot.run.starting ? "checking" : snapshot.run.status) +
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
  const shaped = new Set(snapshot.pieces.filter(function (p) {
    return p.lane === "shaped";
  }).map(function (p) { return p.number; }));
  ticked.forEach(function (n) { if (!shaped.has(n)) { ticked.delete(n); } });
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

button.onclick = function () {
  answer.replaceChildren();
  busy = true;
  refreshButton();
  say("Checking that the run can walk away.");
  fetch("/api/run", {
    method: "POST",
    headers: {"Content-Type": "application/json", "X-Loop-Token": token},
    body: JSON.stringify({pieces: Array.from(ticked),
                          keep_going: document.getElementById("keep-going").checked})
  }).then(function (response) {
    return response.json().then(function (data) { return {ok: response.ok, data: data}; });
  }).then(function (result) {
    answer.replaceChildren();
    if (result.ok) {
      say("Run started (pid " + result.data.pid + "). Log: " + result.data.log);
      (result.data.warnings || []).forEach(function (text) { say("Warning: " + text); });
      ticked.clear();
    } else {
      say("Not started: " + result.data.error);
      (result.data.checks || []).forEach(function (check) {
        say((check.ok ? "ok: " : "failed: ") + check.what + (check.next ? " Fix: " + check.next : ""));
      });
    }
  }).catch(function () {
    answer.replaceChildren();
    say("Could not reach the dashboard server.");
  }).then(function () {
    busy = false;
    refreshButton();
  });
};
