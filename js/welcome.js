function welcome(){
    let welcome_text = 'welcome to my blog'
    if(document.referrer!==''){
        let referrer=document.referrer.split("/")[2];
        welcome_text="欢迎你，来自"+referrer.toUpperCase()+"的朋友";
        if(referrer.toUpperCase()==document.domain.toUpperCase())return;
    }
    swal({
        title: " 很高兴遇见你",
        text: welcome_text+'\n茫茫网络，你是怎么找到我的？',
        imageUrl: "/img/avatar.jpg",
        timer: 3000,
        showConfirmButton: false
    });
}
$(document).ready(()=>{
    welcome()
})

