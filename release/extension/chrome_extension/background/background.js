chrome.runtime.onMessage.addListener(
function(request,sender,sendResponse){

if(request.action==="captureUrl"){

fetch("http://127.0.0.1:8000/download",{
method:"POST",
headers:{
"Content-Type":"application/json"
},
body:JSON.stringify({
url:request.url
})
})
.then(r=>r.json())
.then(data=>{

if(data.playerUrl){
chrome.tabs.create({
url:data.playerUrl
});
}

sendResponse({
success:true
});

})
.catch(err=>{
console.error(err);

sendResponse({
success:false
});
});

return true;
}

});