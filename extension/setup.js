"use strict";

const ext = globalThis.browser ?? globalThis.chrome;
const NEXUS_PAGES = ["https://www.nexusmods.com/*/mods/*"];

function showDone() {
  document.getElementById("allow").hidden = true;
  document.getElementById("done").style.display = "block";
}

ext.permissions.contains({ origins: NEXUS_PAGES }).then((granted) => {
  if (granted) {
    showDone();
  }
});

document.getElementById("allow").addEventListener("click", () => {
  // The request must start directly from the click, with nothing awaited before it.
  ext.permissions.request({ origins: NEXUS_PAGES }).then((granted) => {
    if (granted) {
      showDone();
    }
  });
});
