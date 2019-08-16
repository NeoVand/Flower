function make_curve_points(samples,latent,dual,d=7,h=10){
    // console.log(`latent has ${latent.length} length and ${latent[0].length} dims `)
    let curves = new THREE.Group();
    const dual_sep = 12;
    const moments = samples.length;
    const channels  = dual ? (samples[0].length)/2 : samples[0].length

    function ringmap(vals,i,offset=0,ccw = true,amp=1){
        var vector = vals.map(function(v,k){
            var theta = (k/channels)*2*Math.PI
            var r = 0.5+(d+amp*v)*i/moments;
            var x = ccw? offset+r*Math.cos(theta) : offset-r*Math.cos(theta)
            var y = r*Math.sin(theta);
            var z = h-i*(h/moments);
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
        var pointsR = curveR.getPoints( 10+i );
        var geometryR = new THREE.BufferGeometry().setFromPoints( pointsR );
        var materialR = new THREE.LineBasicMaterial( { color : col,blending: THREE.NormalBlending,
            transparent: true,
            depthTest: true,
            opacity:0.7*i/moments} );
        var curveObjectR = new THREE.Line( geometryR, materialR );
        return curveObjectR;
    }

    if(dual){
    
        for(let i=0;i<moments;i++){
            var valsR = samples[i].slice(0,channels);
            var valsL = samples[i].slice(channels,2*channels);
            var col = colormap(latent[i]);
            
            valsR = ringmap(valsR,i,dual_sep,true,2);
            curveR = make_curve_obj(valsR,i,col);
            curves.add(curveR);

            valsL = ringmap(valsL,i,-dual_sep,false,2);
            curveL = make_curve_obj(valsL,i,col);
            curves.add(curveL);
        }
    } else{
    
    for(let i=0;i<moments;i++){
        var vals = samples[i];
        var col = colormap(latent[i]);
        vals = ringmap(vals,i);
        curve = make_curve_obj(vals,i,col);
        curves.add(curve);
    }

    }
    curves.name = "group";
    return curves;
}

function display(edf,latent,dual,lbls,scene){
    scene.children.forEach(child => (child.name == "group" ) ? scene.remove(child) : null)
    scene.children.forEach(child => (child.name == "guide" ) ? scene.remove(child) : null)
    curves = make_curve_points(edf,latent,dual);
    scene.add(curves);

    // console.log('making the guide:')

    // var can = document.createElement('canvas'),
    // ctx = can.getContext('2d');
 
    // // can.width = 20;
    // // can.height = 20;
 
    // ctx.fillStyle = '#12ff10';
    // ctx.fillRect(3, 3, can.width/2, can.height/2);
    // ctx.strokeStyle = '#ff00ff';
    // ctx.strokeRect(0, 0, can.width/3, can.height/3);

    // var texture = new THREE.Texture(can);
 
    // // MATERIAL
    // var material = new THREE.MeshBasicMaterial({
    //         map: texture,
    //         // transparent: true,
    //         opacity: 0.99,
    //         side: THREE.DoubleSide,
    //         alphaTest: 0.1

    //     });


    // var geometry = new THREE.PlaneGeometry( 20, 20, 20 );
    // // var material = new THREE.MeshBasicMaterial( {color: 0xffff00, side: THREE.DoubleSide, opacity:0.5} );
    // var plane = new THREE.Mesh( geometry, material );
    // plane.name = "guide"
    // scene.add( plane );

}

//#######################################################################################################

function prepare(){
    var clock = new THREE.Clock();
    const canvas = document.querySelector('#c');
    var devicePixelRatio = window.devicePixelRatio || 1;
    canvas.width = window.innerWidth * devicePixelRatio;
    canvas.height = window.innerHeight * devicePixelRatio;
    const scene = new THREE.Scene();

    const renderer = new THREE.WebGLRenderer({canvas: canvas, antialias: true});
    renderer.setPixelRatio( devicePixelRatio );
    renderer.toneMapping = THREE.LinearToneMapping;
    // const camera = new THREE.PerspectiveCamera(fov, aspect, near, far);
    const camera = new THREE.OrthographicCamera( window.innerWidth / - 100, window.innerWidth / 100, window.innerHeight / 100, window.innerHeight / - 100, 0, 2000 );
    camera.position.z = - 10;
    camera.zoom = 0.5;
    camera.updateProjectionMatrix();
    camera.lookAt(new THREE.Vector3(0,0,0));
    // renderer.render(scene,camera)

    var controls = new THREE.OrbitControls( camera, renderer.domElement );
    controls.maxPolarAngle = Math.PI * 0.5;
    controls.minDistance = 0.01;
    controls.maxDistance = 10;
    controls.update();

    var params = {
        exposure: 1,
        bloomStrength: 2.5,
        bloomThreshold: 0,
        bloomRadius: 0
    };

    var renderScene = new THREE.RenderPass( scene, camera );
    var bloomPass = new THREE.UnrealBloomPass( new THREE.Vector2( window.innerWidth, window.innerHeight ), 1.5, 0.4, 0.85 );
    bloomPass.threshold = params.bloomThreshold;
    bloomPass.strength = params.bloomStrength;
    bloomPass.radius = params.bloomRadius;
    composer = new THREE.EffectComposer( renderer );
    composer.addPass( renderScene );
    composer.addPass( bloomPass );

    window.onresize = function () {
        var width = window.innerWidth;
        var height = window.innerHeight;

        var devicePixelRatio = window.devicePixelRatio || 1;
        canvas.width = width * devicePixelRatio;
        canvas.height = width * devicePixelRatio;
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
        renderer.setSize( width, height );
        renderer.setPixelRatio(devicePixelRatio);

        composer.setSize( width*devicePixelRatio, height*devicePixelRatio );
    };

    function animate() {
        requestAnimationFrame( animate );
        // const delta = clock.getDelta();
        composer.render();}

    animate();
    

    // controls.addEventListener('change', requestRenderIfNotRequested);
    // window.addEventListener('resize', requestRenderIfNotRequested);
    return scene
}