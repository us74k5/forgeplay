(function(){

function isVideo(url){
try{
let u=new URL(url);

return (
(u.pathname==="/watch" && u.searchParams.has("v")) ||
u.pathname.startsWith("/shorts/")
);

}catch(e){
return false;
}
}

function sendVideo(url){
chrome.runtime.sendMessage({
action:"captureUrl",
url:url
});
}

document.addEventListener(
"mousedown",
function(e){

const a=e.target.closest("a");

if(!a) return;

if(!isVideo(a.href)) return;

e.preventDefault();
e.stopPropagation();
e.stopImmediatePropagation();

sendVideo(a.href);

return false;

},
true
);


document.addEventListener(
"click",
function(e){

const a=e.target.closest("a");

if(!a) return;

if(!isVideo(a.href)) return;

e.preventDefault();
e.stopPropagation();
e.stopImmediatePropagation();

return false;

},
true
);

console.log("interceptor loaded");

})();