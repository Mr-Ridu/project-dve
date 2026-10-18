// Version: 1.0.0  
(function(w,d,t,r,u){  
    var f,n,i;  
    w[u]=w[u]||[],f=function(){  
        var o={ti: uet_tag_data.uet_tag_id, enableAutoSpaTracking: uet_tag_data.enableAutoSpaTracking, tm:"wpp_1.0.7"};  
        o.q=w[u],w[u]=new UET(o),w[u].push("pageLoad")  
    },  
    n=d.createElement(t),n.src=r,n.async=1,n.onload=n.onreadystatechange=function(){  
        var s=this.readyState;  
        s&&s!=="loaded"&&s!=="complete"||(f(),n.onload=n.onreadystatechange=null)  
    },  
    i=d.getElementsByTagName(t)[0],i.parentNode.insertBefore(n,i)  
})(window,document,"script","../bat.bing.com/bat.js","uetq");  