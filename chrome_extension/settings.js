document.addEventListener(
"DOMContentLoaded",
function(){

chrome.storage.sync.get(
[
"enabled",
"quality",
"helperUrl"
],
function(s){

document.getElementById(
"enabled"
).checked=
s.enabled !== false;

document.getElementById(
"quality"
).value=
s.quality || "720";

document.getElementById(
"helperUrl"
).value=
s.helperUrl ||
"http://127.0.0.1:8000/download";

}
);

document.getElementById(
"save"
).addEventListener(
"click",
function(){

chrome.storage.sync.set({

enabled:
document.getElementById(
"enabled"
).checked,

quality:
document.getElementById(
"quality"
).value,

helperUrl:
document.getElementById(
"helperUrl"
).value

},
function(){

document.getElementById(
"status"
).innerText="Saved";

setTimeout(
()=>document.getElementById(
"status"
).innerText="",
1500
);

});

}
);

});