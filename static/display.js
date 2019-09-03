
var loader = new THREE.FontLoader();
var DUAL, LABELS, DEPTH
const dual_sep = 10;
var h = 25;

// let vid = document.getElementById('cd');


function make_curve_points(samples,latent,dual){
    let d;
    h=cfg.h;
    // console.log(`latent has ${latent.length} length and ${latent[0].length} dims `)
    let curves = new THREE.Group();
    const moments = samples.length;
    const channels  = dual ? (samples[0].length)/2 : samples[0].length

    function ringmap(vals,i,offset=0,ccw = true,amp=1){
        var vector = vals.map(function(v,k){
            var theta = (k/channels)*2*Math.PI
            var r = 0.1+(d+amp*v)*i/moments;
            var x = ccw? offset+r*Math.cos(theta) : offset-r*Math.cos(theta)
            var y = r*Math.sin(theta);
            var z = i*(h/moments)-h;
            var vec = new THREE.Vector3(x,y,z);
            return vec;
        });
        return vector;
    }

    function colormap(col){
        const scale = 1.;
        var r = scale*col[0];
        var g = scale*col[1];
        var b = scale*col[2];
        var color = new THREE.Color(r,g,b);
        return color;
    }

    function make_curve_obj(valsR,i,col){
        var curveR = new THREE.CatmullRomCurve3( valsR , closed=true, curveType='catmullrom', tension=.8);
        var pointsR = curveR.getPoints( Math.round(10+0.5*i) );
        var geometryR = new THREE.BufferGeometry().setFromPoints( pointsR );
        var materialR = new THREE.LineBasicMaterial( { color:cfg.bw ? 0xffffff : col,blending: THREE.NormalBlending,
            transparent: true,
            depthTest: true,
            opacity:i/moments} );
        var curveObjectR = new THREE.Line( geometryR, materialR );
        return curveObjectR;
    }

    if(dual){
        d=6.5;    
        for(let i=0;i<moments;i++){
            var valsR = samples[i].slice(0,channels);
            var valsL = samples[i].slice(channels,2*channels);
            var col = colormap(latent[i]);
            
            valsR = ringmap(valsR,i,dual_sep,true,cfg.amp);
            curveR = make_curve_obj(valsR,i,col);
            curves.add(curveR);

            valsL = ringmap(valsL,i,-dual_sep,false,cfg.amp);
            curveL = make_curve_obj(valsL,i,col);
            curves.add(curveL);
        }
    } else{
        d=11;    
    for(let i=0;i<moments;i++){
        var vals = samples[i];
        var col = colormap(latent[i]);
        vals = ringmap(vals,i,0,true,cfg.amp);
        curve = make_curve_obj(vals,i,col);
        curves.add(curve);
    }

    }
    curves.name = "group";
    return curves;
}

function display(edf,latent,dual,scene){
    scene.children.forEach(child => (child.name == "group" ) ? scene.remove(child) : null)
    curves = make_curve_points(edf,latent,dual);
    scene.add(curves);
    DUAL = dual;
    DEPTH = cfg.depth
    scene.children.forEach(function(child){
        if(child.name == "group"){
            child.traverse( function( node ) {
                if( node.material ) {
                    node.material.opacity = cfg.opacity;
                    // node.material.transparent = true;
                }
            });
        }
    })
}

function updateScene(cfg){

    scene.children.forEach(function(child){
        if(child.name == "group"){
            child.traverse( function( node ) {
                if( node.material ) {
                    node.material.opacity = cfg.opacity;
                    // node.material.transparent = true;
                }
            });
        }
    })

    var LABELS = cfg.labels;

    function make_guide(lbls,size = 10.5, ccw =1){
        let guide = new THREE.Group();

        var radius = size;
        var radialSegments = 100;
        var material = new THREE.MeshBasicMaterial({
        color: 0x090909,
        });
        var hemiSphereGeom = new THREE.SphereBufferGeometry(radius, radialSegments, Math.round(radialSegments / 4), 0, Math.PI * 2, 0, Math.PI * 0.5);
        var hemiSphere = new THREE.Mesh(hemiSphereGeom, material);
        hemiSphere.rotation.x = -Math.PI/2;
        // hemiSphere.scale.y = 2;
        guide.add(hemiSphere);






        var rgeometry = new THREE.RingGeometry( size-1, size-1+0.05, 100 );
        var rmaterial = new THREE.MeshBasicMaterial( { color: 0xffffff, side: THREE.DoubleSide, transparent:true, opacity:0.2 } );
        var rmesh = new THREE.Mesh( rgeometry, rmaterial );
        guide.add( rmesh );

        var lgeometry =  new THREE.Geometry();
        lgeometry.vertices.push(new THREE.Vector3( 0, 0, -h) );
        lgeometry.vertices.push(new THREE.Vector3( 0.75*size, 0, 0) );
        var lmaterial = new THREE.LineBasicMaterial( {
            color: 0xffffff,
            transparent:true,
            opacity:0.3
        } );
        var ruler = new THREE.Line( lgeometry, lmaterial );
        guide.add(ruler);

        const font_url = Flask.url_for("static", {"filename": "Courier New_Regular.json"});
    
        loader.load(font_url, function ( font ) {
            for(var i=0;i<lbls.length;i++){

                var tgeometry = new THREE.TextGeometry(lbls[i], {
                    font:font,
                    size: 0.5,
                    height: 0.01,
                    curveSegments: 5,
                } );

                tgeometry.center();
                var tmesh = new THREE.Mesh( tgeometry, rmaterial );
                tmesh.position.x = ccw*size * Math.cos(i*2*Math.PI/lbls.length);
                tmesh.position.y = size * Math.sin(i*2*Math.PI/lbls.length);
                
                if (i<=(lbls.length/4) || i>=(3*(lbls.length/4))){
                    tmesh.rotation.z = ccw*i*2*Math.PI/lbls.length}
                else{
                    tmesh.rotation.z =Math.PI + ccw*i*2*Math.PI/lbls.length}
                
                guide.add(tmesh);
            }

            var ruler_label = DEPTH/sps;
            var rtgeometry = new THREE.TextGeometry(ruler_label+' sec', {
                font:font,
                size: 0.5,
                height: 0.01,
                curveSegments: 5,
            } );
            var rtmaterial = new THREE.MeshBasicMaterial( { color: 0xffffff, side: THREE.DoubleSide, transparent:true, opacity:0.2 } );
            rtgeometry.center();
            var rtmesh = new THREE.Mesh( rtgeometry, rtmaterial );
            rtmesh.position.x = 0.5*size;
            rtmesh.position.y = 0.05*size;
            rtmesh.position.z = - 0.5*size;
            rtmesh.rotation.y = -Math.PI/4.5;
            guide.add(rtmesh)
            
        } );
        return guide;

    }

    if(cfg.dual!=DUAL ||  cfg.depth!=DEPTH){
        scene.children.forEach(child => (child.name == "guide" ) ? scene.remove(child) : null);
        DUAL = cfg.dual;
        DEPTH =  cfg.depth;
    }

    if(!scene.getObjectByName('guide')){
        
        if(DUAL){
        console.log("from display: ",LABELS);
        var lblsR = LABELS.slice(0,LABELS.length/2);
        var lblsL = LABELS.slice(LABELS.length/2,LABELS.length);
        var guides = new THREE.Group();
        guideR = make_guide(lblsR,9.1);
        guideR.position.x = dual_sep;
        guides.add(guideR);
        guideL = make_guide(lblsL,9.1,-1);
        guideL.position.x = -dual_sep;
        guides.add(guideL);

        guides.name = 'guide';
        scene.add(guides);

        }
    
        else{
        var lbls = LABELS;
        let guide = make_guide(lbls,14.5);
        guide.name = 'guide';
        scene.add(guide);
        
    
        }

    }
}

function transpose(array){
    newArray = array[0].map(function(col, i){
        return array.map(function(row){
            return row[i];
        });
    });
    return newArray
} 

function clearScene(){
    scene.children.forEach(child => (child.name == "guide" ) ? scene.remove(child) : null);
    scene.children.forEach(child => (child.name == "group" ) ? scene.remove(child) : null);
};

function linedisplay(edf,latent,scene){
    scene.children.forEach(child => (child.name == "group" ) ? scene.remove(child) : null)
    var  lines = make_lines(edf,latent);
    scene.add(lines);
}

function make_lines(samples,latent){
    let lines = new THREE.Group();
    let chans = transpose(samples);
    let chanCount =chans.length;
    let W = canvas.width/100;
    let H = canvas.height/100;
    function chanmap(vals,i,amp=1){
        var vector = vals.map(function(v,k){
            var x = -W/2+k*W*cfg.step/cfg.depth
            var y = -H/2+i*1.5+amp*v
            var z = 0
            var vec = new THREE.Vector3(x,y,z);
            return vec;
        });
        return vector;
    }

    function make_line_obj(valsR,i){
        var curveR = new THREE.CatmullRomCurve3( valsR , closed=false, curveType='catmullrom', tension=.8);
        var pointsR = curveR.getPoints( Math.round(cfg.depth/cfg.step) );
        var geometryR = new THREE.BufferGeometry().setFromPoints( pointsR );
        var materialR = new THREE.LineBasicMaterial( { color:0xffffff,blending: THREE.NormalBlending,
            transparent: true,
            depthTest: true,
            opacity:cfg.opacity} );
        var curveObjectR = new THREE.Line( geometryR, materialR );
        return curveObjectR;
    }

    for(let i=0;i<chanCount;i++){
        var vals = chans[i];
        vals = chanmap(vals,i,cfg.amp);
        curve = make_line_obj(vals,i);
        lines.add(curve);
    }

    lines.name = "group";
    return lines;
    
}


//#######################################################################################################

function prepare(){
    var size = 0.7*window.innerWidth;
    var clock = new THREE.Clock();
    const canvas = document.querySelector('#c');
    var devicePixelRatio = window.devicePixelRatio || 1;
    canvas.width = size * devicePixelRatio;
    canvas.height = size * devicePixelRatio;
    const scene = new THREE.Scene();

    {
        const color = 0x010101;  // white
        const near = 1;
        const far = 100;
        scene.fog = new THREE.Fog(color, near, far);
    }


    var context = canvas.getContext( 'webgl2' );
    var renderer = new THREE.WebGLRenderer( { canvas: canvas, context: context,  antialias: true } );

    // const renderer = new THREE.WebGLRenderer({canvas: canvas, antialias: true});
    renderer.setPixelRatio( devicePixelRatio );
    // renderer.toneMapping = THREE.LinearToneMapping;
    // const camera = new THREE.PerspectiveCamera(fov, aspect, near, far);
    const camera = new THREE.OrthographicCamera( size / - 100, size / 100, size / 100, size / - 100, 0, 2000 );
    camera.position.z = 30;
    camera.zoom = 0.45;
    camera.updateProjectionMatrix();
    camera.lookAt(new THREE.Vector3(0,0,0));
    // renderer.render(scene,camera)

    // var controls = new THREE.OrbitControls( camera, renderer.domElement );
    // // controls.maxPolarAngle = Math.PI * 0.5;
    // controls.autoRotate = rotate;
    // controls.minDistance = 0.01;
    // controls.maxDistance = 10;
    // // controls.maxAzimuthAngle = Math.PI * 0.5;
    // controls.update();

    var params = {
        exposure: 1,
        bloomStrength: 2.5,
        bloomThreshold: 0,
        bloomRadius: 0
    };

    var renderScene = new THREE.RenderPass( scene, camera );
    var bloomPass = new THREE.UnrealBloomPass( new THREE.Vector2( size, size ), 1.5, 0.4, 0.85 );
    bloomPass.threshold = params.bloomThreshold;
    bloomPass.strength = params.bloomStrength;
    bloomPass.radius = params.bloomRadius;
    composer = new THREE.EffectComposer( renderer );
    composer.addPass( renderScene );
    composer.addPass( bloomPass );

    window.onresize = function () {
        size = 0.7*window.innerWidth;
        var width = size;
        var height = size;

        var devicePixelRatio = window.devicePixelRatio || 1;
        canvas.width = width * devicePixelRatio;
        canvas.height = width * devicePixelRatio;
        camera.updateProjectionMatrix();
        renderer.setSize( width, height );
        renderer.setPixelRatio(devicePixelRatio);

        composer.setSize( width*devicePixelRatio, height*devicePixelRatio );
    };

    var mouseX = 0;
    var mouseY = 0;
    // var windowHalfX = canvas.width / 2;
    // var windowHalfY = canvas.height / 2;


    function onDocumentMouseMove( event ) {

        var rect = event.target.getBoundingClientRect();
        mouseX = -( event.clientX - rect.right/2 ) / 20;
        mouseY = -( event.clientY - rect.bottom/2 ) / 20;

    }
    function onMouseExitCanvas( event ){
        mouseX = 0;
        mouseY = 0;
    }

    canvas.addEventListener( 'mousemove', onDocumentMouseMove, false );
    canvas.addEventListener('mouseleave', onMouseExitCanvas , false);

    function animate() {
        // controls.update();
        var timer = 0.0001 * Date.now();

        camera.position.x += ( mouseX - camera.position.x ) * .1;
        camera.position.y += ( - mouseY - camera.position.y ) * .1;

        camera.lookAt( scene.position );

        requestAnimationFrame( animate );
        // const delta = clock.getDelta();
        composer.render();}

    animate();
    

    // controls.addEventListener('change', requestRenderIfNotRequested);
    // window.addEventListener('resize', requestRenderIfNotRequested);
    return scene
}

// setInterval(function(){
//     var  video = document.getElementById('cd'); 
//     var t = Math.round(video.currentTime);
//             // console.log(t);
//     cfg.frame = start_sample+t*500+cfg.depth;
//     requestData();
//  }, 100);

