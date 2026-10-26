/* Remote and PC edit the same launcher preferences. No arbitrary commands or file paths. */
(() => {
  let loaded = null, city = null, picture = null, searchResults = [];
  let personalBusy = false;
  const panel = $('personal-panel');
  const val = (key, fallback) => loaded?.values?.[key] ?? loaded?.effective?.[key] ?? fallback;
  const field = (label, control) => `<label class="field">${label}${control}</label>`;
  function draw() {
    panel.innerHTML = `<div class="card-heading"><h2>Cá nhân hóa TV</h2><button class="icon-btn" data-personal="close" aria-label="Đóng cá nhân hóa">×</button></div>
      <p>Chỉnh bằng máy tính hoặc mở thiết lập trên TV để dùng điều khiển. Hai cách dùng chung dữ liệu. Kết nối TV và Giữ launcher trước khi thử giao diện.</p><p class="muted">Sau khi chỉnh bằng remote, bấm Đọc thiết lập trên TV để cập nhật biểu mẫu. Trong lúc máy tính đang thử, không chỉnh thêm giao diện ở nơi khác; hãy thử các chức năng rồi Giữ hoặc Hoàn tác trước.</p>
      <div class="two-buttons">${button('Đọc thiết lập trên TV','personal_read','secondary',busy||!state.device)}<button class="btn secondary" data-personal="open" ${busy||!state.device?'disabled':''}>Mở Cá nhân hóa trên TV</button></div>
      <details><summary>Chuẩn bị lần đầu / cập nhật từ bản cũ</summary><p>Build bản launcher có phần cá nhân hóa, rồi cập nhật và thử Home trong 3 phút. Cập nhật giữ dữ liệu ứng dụng; hoàn tác đưa Home về trạng thái trước đó, không hạ phiên bản APK.</p>
        <label class="check"><input id="personal-license" type="checkbox"><span>Tôi đã đọc và chấp nhận <a href="https://developer.android.com/studio/terms" target="_blank" rel="noreferrer">giấy phép Android SDK</a>.</span></label>
        <div class="two-buttons"><button class="btn secondary" data-personal="build">1. Build launcher</button><button class="btn secondary" data-personal="update" ${!state.device?'disabled':''}>2. Sao lưu, cập nhật và thử</button></div><a href="/api/build-log" target="_blank">Xem nhật ký build</a></details>
      ${!loaded?notice('Bấm Đọc thiết lập sau khi đã cài bản launcher hỗ trợ Cá nhân hóa. Không cần nhập model TV.'):`<div class="personal-preview" id="personal-preview"><small>MÔ PHỎNG BỐ CỤC · KHÔNG PHẢI ẢNH TV</small><h3 id="preview-greeting"></h3><strong>20:30</strong><p>Ngày dương lịch <span id="preview-lunar"></span></p><div id="preview-tiles"></div></div>
        <div class="field-row">${field('Số ứng dụng mỗi hàng',`<select id="personal-columns">${[4,5,6,7].map(n=>`<option ${val('columns',5)===n?'selected':''}>${n}</option>`).join('')}</select>`)}${field('Màu nền',`<input id="personal-color" type="color" value="${esc(val('cyt_background','#101827'))}">`)}</div>
        <div class="field-row">${field('Tên trong lời chào',`<input id="personal-name" maxlength="60" value="${esc(val('cyt_name',''))}" placeholder="Ví dụ: Gia đình tôi">`)}${field('Độ tối ảnh nền',`<select id="personal-dim">${[0,20,40,60,80,90].map(n=>`<option value="${n}" ${val('cyt_dim',40)===n?'selected':''}>${n}%</option>`).join('')}</select>`)}</div>
        <label class="check"><input id="personal-lunar" type="checkbox" ${val('cyt_lunar',false)?'checked':''}><span>Hiện ngày âm bên dưới ngày dương · lịch Việt Nam, UTC+7</span></label>
        <label class="check"><input id="personal-greeting" type="checkbox" ${val('cyt_greeting',true)?'checked':''}><span>Hiện lời chào</span></label>
        <label class="check"><input id="personal-motion" type="checkbox" ${val('animations',true)?'checked':''}><span>Hiệu ứng chuyển động trong launcher</span></label>
        ${field('Ảnh nền đã lưu trên TV',`<select id="personal-picture"><option value="">Theo giao diện mặc định</option><option value="none" ${val('wallpaper_choice','')==='none'?'selected':''}>Không dùng ảnh nền</option>${(loaded.pictures||[]).map(name=>`<option value="${esc(name)}" ${val('wallpaper_choice','')===name?'selected':''}>${esc(name)}</option>`).join('')}</select>`)}
        ${field('Thêm ảnh từ máy tính', '<input id="personal-file" type="file" accept="image/jpeg,image/png,image/webp">')}<p class="muted">Ảnh được thu nhỏ tối đa 1920 × 1080 trước khi gửi; tối đa 12 ảnh cá nhân. Trên TV có thể chọn ảnh đã lưu hoặc mở trình chọn ảnh TV/USB nếu có.</p>
        <div class="two-buttons"><button class="btn" data-personal="apply" ${busy?'disabled':''}>Thử thiết lập trong 3 phút</button><button class="btn secondary" data-personal="reset" ${busy?'disabled':''}>Thử trở về mặc định</button></div>`}
      <hr><h3>Thời tiết · tùy chọn</h3><p>Một ô mở trang thời tiết trên TV, có ngày hiện tại và dự báo. Không phải tiện ích nhiệt độ cập nhật liên tục trên Home. Chọn thành phố bằng TV hoặc tìm trên máy tính; không tự lấy GPS.</p>
      <p class="muted">Tìm địa điểm gửi tên vừa nhập đến Open-Meteo / GeoNames; mô-đun gửi tọa độ thành phố khi tải dự báo. Không cần tài khoản cá nhân. Internet chỉ cần cho phần thời tiết.</p>
      <div class="two-buttons"><button class="btn secondary" data-personal="build-weather">1. Build Thời tiết</button><button class="btn secondary" data-personal="install-weather" ${!state.device?'disabled':''}>2. Cài Thời tiết</button><button class="btn secondary" data-personal="weather-open" ${!state.device?'disabled':''}>Mở / đổi thành phố trên TV</button></div>
      ${field('Tìm thành phố', '<input id="personal-city-query" placeholder="Ví dụ: Cần Thơ">')}<button class="btn secondary" data-personal="search" ${busy?'disabled':''}>Tìm thành phố</button><div id="personal-cities"></div><p id="personal-city-selected"></p>
      <p class="muted">${loaded?.weather?.name?'Thành phố đang lưu: '+esc(loaded.weather.name):'Chưa đọc được thành phố đã lưu.'} Sau khi chọn thành phố, bấm Thử thiết lập để lưu cùng lần thử.</p>
      <p class="muted">Sau khi Giữ và tắt gỡ lỗi, vẫn chỉnh trực tiếp bằng điều khiển TV. Muốn chỉnh từ máy tính cần bật gỡ lỗi và kết nối lại. Các ảnh và mô-đun đã thêm được giữ lại khi hoàn tác thiết lập.</p>`;
    preview();
  }
  function preview() {
    if(!$('personal-preview'))return;
    $('personal-preview').style.backgroundColor=$('personal-color').value;
    $('preview-greeting').textContent=$('personal-greeting').checked?'Chào buổi tối'+($('personal-name').value?' · '+$('personal-name').value:''):'';
    $('preview-lunar').textContent=$('personal-lunar').checked?' · Ngày âm Việt Nam':'';
    $('preview-tiles').innerHTML=Array.from({length:Number($('personal-columns').value)},()=>'<span>Ứng dụng</span>').join('');
    $('preview-tiles').style.gridTemplateColumns=`repeat(${$('personal-columns').value},1fr)`;
  }
  async function ensureBackup() {
    await run('backup');
    // Wait for the normal status poll to receive the completed job.
    for(let n=0;n<90;n++){
      await new Promise(resolve=>setTimeout(resolve,500));await poll();
      if(!busy){if(state.job?.action==='backup'&&state.job.status==='done')return state.job.result.backup;throw Error(state.job?.error||'Chưa tạo được bản lưu.');}
    }
    throw Error('Sao lưu đang chạy. Chờ hoàn tất rồi thử lại.');
  }
  panel.addEventListener('input',preview);
  panel.addEventListener('change',async event=>{
    if(event.target.id!=='personal-file'||!event.target.files?.length)return;
    try{
      if(busy||personalBusy)throw Error('Chờ bước đang chạy hoàn tất.');
      const file=event.target.files[0];if(file.size>20_000_000)throw Error('Ảnh gốc tối đa 20 MB.');
      const image=await createImageBitmap(file,{resizeWidth:1920,resizeQuality:'high'});
      const scale=Math.min(1,1920/image.width,1080/image.height),canvas=document.createElement('canvas');
      canvas.width=Math.max(1,Math.round(image.width*scale));canvas.height=Math.max(1,Math.round(image.height*scale));canvas.getContext('2d').drawImage(image,0,0,canvas.width,canvas.height);image.close();
      let data=canvas.toDataURL('image/jpeg',0.8).split(',')[1];if(data.length>666668)data=canvas.toDataURL('image/jpeg',0.5).split(',')[1];
      if(data.length>666668)throw Error('Ảnh vẫn quá lớn sau thu nhỏ. Chọn ảnh khác.');
      await run('personal_upload',{data});
    }catch(error){toast(error.message);}
  });
  panel.addEventListener('click',async event=>{
    const control=event.target.closest('[data-personal]');if(!control)return;
    const action=control.dataset.personal;
    try{
      if(action==='close'){panel.classList.add('hidden');return;}
      if(busy||personalBusy)throw Error('Chờ bước đang chạy hoàn tất.');
      personalBusy=true;
      if(action==='open'||action==='weather-open'){await run('personal_open',{weather:action==='weather-open'});return;}
      if(action==='build'||action==='build-weather'){
        const licenses=$('personal-license')?.checked===true;
        if(!licenses)throw Error('Mở Chuẩn bị lần đầu và xác nhận giấy phép Android SDK trước khi build.');
        await run(action==='build'?'build':'build_weather',{licenses});return;
      }
      if(action==='install-weather'){await run('install_weather');return;}
      if(action==='search'){await run('city_search',{name:$('personal-city-query').value});return;}
      if(action.startsWith('city-')){city=searchResults[Number(action.slice(5))];$('personal-city-selected').textContent='Đã chọn: '+city.name;return;}
      if(action==='update'){const id=await ensureBackup();await run('update_launcher',{backup:id});return;}
      if(action==='apply'||action==='reset'){
        if(!loaded)throw Error('Đọc thiết lập trên TV trước.');
        const values=action==='reset'?Object.fromEntries(Object.keys(loaded.values).map(key=>[key,null])):{columns:Number($('personal-columns').value),cyt_background:$('personal-color').value,cyt_name:$('personal-name').value.trim(),cyt_dim:Number($('personal-dim').value),cyt_lunar:$('personal-lunar').checked,cyt_greeting:$('personal-greeting').checked,animations:$('personal-motion').checked,advanced_effects:false,wallpaper_choice:$('personal-picture').value||null};
        const id=await ensureBackup();await run('personal_apply',{backup:id,values,...(city&&action==='apply'?{city}:{})});return;
      }
    }catch(error){toast(error.message);}finally{personalBusy=false;}
  });
  $('personal-open').addEventListener('click',()=>{panel.classList.remove('hidden');if(!panel.innerHTML)draw();panel.scrollIntoView({behavior:'smooth'});});
  window.CleanupPersonalize={result(job){
    if(job.status!=='done')return;
    if(job.action==='personal_read'){loaded=job.result;city=null;draw();}
    if(job.action==='personal_upload'){
      picture=job.result.picture;
      if(loaded&&!loaded.pictures.includes(picture))loaded.pictures.push(picture);
      const option=document.createElement('option');option.value=picture;option.textContent=picture;$('personal-picture').appendChild(option);$('personal-picture').value=picture;
    }
    if(job.action==='city_search'){searchResults=job.result.cities||[];$('personal-cities').innerHTML=searchResults.length?searchResults.map((place,n)=>`<button class="btn secondary small" data-personal="city-${n}">${esc(place.name)}</button>`).join(''):'Không tìm thấy. Thử tên khác, ví dụ Ho Chi Minh City.';}
    if(['personal_apply','update_launcher'].includes(job.action)&&job.result.backup){backup=job.result.backup;completed.delete(4);renderTrial();$('trial-panel').scrollIntoView({behavior:'smooth'});}
    if(job.action==='connect'){loaded=null;city=null;draw();}
  }};
})();
