var riverApp = angular.module('riverApp', ['angularMoment', 'ngSanitize']);

riverApp.constant('angularMomentConfig', {
    preprocess: 'utc',
});

riverApp.controller('RiverController', ['$scope', '$http', function($scope, $http) {
    $scope.$watch('currentRiver', function() {
	if ($scope.currentRiver) {
	    $http.get($scope.currentRiver.url).success(function(obj) {
		$scope.riverObj = obj;
	    });
	}
    });

    $http.get('manifest.json').success(function(obj) {
	$scope.rivers = obj;
	$scope.currentRiver = obj[0];
    });
}]);
