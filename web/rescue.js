(() => {
  const panel=$('rescue-panel');let report=null,waiting=false;
  function draw(){
    panel.innerHTML=`<div class="card-heading"><h2>Hỗ trợ TV đã chỉnh bằng công cụ khác</h2><button class="icon-btn" data-rescue="close" aria-label="Đóng hỗ trợ">×</button></div>
      ${notice('<b>Không tìm thấy bản lưu cũ không có nghĩa là TV chưa từng được chỉnh.</b> Nếu ban đầu bạn không dùng <b>Thanh Tùng Tiên Sinh Cleanup</b>, hoặc đã mất bản lưu/chuyển máy tính, chương trình không biết chính xác trạng thái ban đầu. Chức năng này chỉ hỗ trợ kiểm tra và thử chuyển về Màn hình chính hệ thống còn trên TV.',true)}
      <ol class="guide-list"><li><b>TV đã tắt gỡ lỗi?</b><p>Mở Cài đặt trên TV → Tùy chọn nhà phát triển → bật lại gỡ lỗi thích hợp và chấp nhận máy tính. Quay về bước Kết nối. Chương trình không thể tự bật gỡ lỗi từ máy tính khi chưa có quyền.</p></li><li><b>Kiểm tra trước khi thay đổi.</b><p>Đọc các ứng dụng Home được hệ thống nhận diện, kể cả gói đang bị tắt. Không tự bật lại hàng loạt ứng dụng hoặc tải APK launcher gốc từ nơi khác.</p></li><li><b>Thử trước rồi Giữ.</b><p>Tạo bản lưu trạng thái hiện tại, thử Home được chọn trong 3 phút. Hoàn tác quay về trước lần hỗ trợ này; không khôi phục toàn bộ thay đổi cũ hoặc factory reset.</p></li></ol>
      <div class="two-buttons"><button class="btn secondary" data-rescue="connect">Quay lại Kết nối</button><button class="btn" data-rescue="inspect" ${busy||!state.device?'disabled':''}>Kiểm tra Home hệ thống</button></div>
      ${report?`<p>${esc(report.message)}</p>${report.hasBackup?notice('Có bản lưu trên máy; xem Mở khôi phục trước. Bản lưu được tạo sau khi chỉnh bằng công cụ khác không ghi lại được trạng thái trước đó.'):''}<p class="muted">Home hiện tại: <code>${esc(report.currentHome||'Không xác minh được')}</code></p>
      ${!report.canTrial?notice('Không xác minh được Home hiện tại để bảo đảm quay lại. Chương trình chỉ chẩn đoán; hãy dùng Cài đặt → Ứng dụng mặc định → Màn hình chính trên TV hoặc hỗ trợ của hãng.',true):''}
      ${report.candidates.length?`<label class="field">Màn hình chính hệ thống do TV báo cáo<select id="rescue-choice">${report.candidates.map(item=>`<option value="${esc(item.component)}">${esc(item.package)} · ${item.disabled?'Đang bị tắt':'Đang bật'}</option>`).join('')}</select></label>
      <label class="check"><input id="rescue-ack" type="checkbox"><span>Tôi hiểu đây chỉ là thử chuyển Home, không phục hồi chính xác mọi thay đổi trước đây.</span></label><button class="btn" data-rescue="apply" ${!report.canTrial||busy?'disabled':''}>Sao lưu và thử Home đã chọn</button>`:notice('Không tìm thấy Home hệ thống đủ điều kiện. Có thể gói đã bị gỡ hoặc firmware không cung cấp dữ liệu; không tự cài lại hoặc suy đoán gói thay thế.',true)}`:''}
      <p class="muted">Không thể cứu TV không khởi động hoặc không có đường kết nối ADB bằng giao diện này. Không cần rút điện để “khôi phục từ đầu”; rút điện không phải factory reset.</p>`;
  }
  $('rescue-open').addEventListener('click',()=>{draw();panel.classList.remove('hidden');panel.scrollIntoView({behavior:'smooth'});});
  panel.addEventListener('click',async event=>{
    const action=event.target.closest('[data-rescue]')?.dataset.rescue;if(!action)return;
    if(action==='close'){panel.classList.add('hidden');return;}
    if(action==='connect'){go(1);return;}
    try{
      if(busy||waiting)throw Error('Chờ bước đang chạy hoàn tất.');
      if(action==='inspect'){await run('rescue_inspect');return;}
      if(action==='apply'){
        if(!$('rescue-ack')?.checked)throw Error('Xác nhận đã hiểu giới hạn trước khi thử.');
        const component=$('rescue-choice').value;waiting=true;
        await run('backup');
        for(let n=0;n<90;n++){
          await new Promise(resolve=>setTimeout(resolve,500));await poll();
          if(!busy){
            if(state.job?.action!=='backup'||state.job.status!=='done')throw Error(state.job?.error||'Chưa tạo được bản lưu.');
            await run('rescue_home',{backup:state.job.result.backup,component,acknowledgeLimitedRecovery:true});return;
          }
        }
        throw Error('Sao lưu đang chạy. Chờ kết quả rồi thử tiếp.');
      }
    }catch(error){toast(error.message);}finally{waiting=false;}
  });
  window.CleanupRescue={result(job){
    if(job.status!=='done')return;
    if(job.action==='rescue_inspect'){report=job.result;draw();}
    if(job.action==='connect'){report=null;if(panel.innerHTML)draw();}
    if(job.action==='rescue_home'){backup=job.result.backup;completed.delete(4);renderTrial();$('trial-panel').scrollIntoView({behavior:'smooth'});}
  }};
})();
