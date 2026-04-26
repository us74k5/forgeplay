chrome.runtime.onMessage.addListener(
async function(request,sender,sendResponse){

if(request.action!=="captureUrl"){
return;
}

try{

chrome.storage.sync.get(
["quality"],
async function(settings){

const quality=settings.quality || "720";

console.log(
"Sending to helper:",
request.url,
"quality:",
quality
);

const r=await fetch(
"http://127.0.0.1:8000/download",
{
method:"POST",
headers:{
"Content-Type":"application/json"
},
body:JSON.stringify({
url:request.url,
quality:quality
})
}
);

const data=await r.json();

console.log(data);

if(data.playerUrl){
chrome.tabs.create({
url:data.playerUrl
});
}

sendResponse({
success:true
});

}
);

return true;

}
catch(e){

console.error(e);

sendResponse({
success:false,
error:String(e)
});

return true;
}

});